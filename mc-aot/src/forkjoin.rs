//! java.util.concurrent.ForkJoinPool — port fiel de ARQUITECTURA (OpenJDK, Doug Lea,
//! public-domain heritage), no de código. Estado: v0.1 experimental, NO cableado al
//! backend traductor todavía; el backend productivo experimental sigue usando rayon.
//!
//! Fidelities kept (architecture level, mirrors ForkJoinPool.java):
//!  - External submissions from non-fork/join clients go to submission queues drained
//!    FIFO; forked (worker-local) work is pushed at the tail (top) and taken LIFO by
//!    the owner — or FIFO from the base when asyncMode (push/poll at base) — while
//!    thieves always take from base. Here v0.1 has no fork()/join(), so only the
//!    submission path exists; the forked path lands with ForkJoinTask proper.
//!  - Parallelism is validated 1..=32767 exactly like the constructor (Java throws
//!    IllegalArgumentException otherwise).
//!  - Termination: shutdown() stops accepting; the pool terminates when quiescent
//!    (no queued and no running tasks); await_termination(timeout) is bounded —
//!    a bounded Java-consistent operation, never an unbounded wait.
//!  - Panicking tasks are counted and do not kill the worker (analogous to the
//!    pool surviving a task that threw, minus Java's UncaughtExceptionHandler
//!    dispatch, which lands with the handler hook).
//!
//! Deliberate divergences from the OpenJDK implementation, on purpose:
//!  - Memory model: a single Mutex<PoolState> + Condvar instead of Unsafe/volatile
//!    lock-free WorkQueue arrays. Same observable semantics, simpler memory model,
//!    slower — this is a reference track, not a hot executor.
//!  - Workers are spawned eagerly at construction, not lazily on demand (FJP spawns
//!    lazily and compensates on blocking joins). Compensation and join-helping
//!    (helpJoin) are NOT implemented in v0.1.
//!  - asyncMode FIFO for worker-local queues cannot be exercised yet (no fork/join);
//!    submission queues are always FIFO, as in FJP.
//!  - No ManagedBlocker / managed compensation, no common pool, no Scheduled methods,
//!    no runState/ctl bit-packing (no steal counts, no toString diagnostics).
//!
//! Every divergence above is a tracked limitation; none is presented as ForkJoinPool
//! parity. Java differential oracles are a separate, pending milestone.
use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// asyncMode flag, mirroring the `asyncMode` constructor parameter.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode {
    /// default: LIFO for worker-local deque
    Lifo,
    /// asyncMode: FIFO everywhere
    Fifo,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PoolError {
    /// java.lang.IllegalArgumentException: parallelism out of range
    IllegalArgument(String),
    /// java.util.concurrent.RejectedExecutionException after shutdown()
    RejectedExecution,
}
impl std::fmt::Display for PoolError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PoolError::IllegalArgument(msg) => write!(f, "IllegalArgumentException: {msg}"),
            PoolError::RejectedExecution => write!(f, "RejectedExecutionException: pool cerrado"),
        }
    }
}
impl std::error::Error for PoolError {}

/// Maximum value accepted by the ForkJoinPool constructor (OpenJDK: MAX_CAP).
pub const MAX_PARALLELISM: usize = 32767;

struct PoolState {
    /// Submission queues: external, non-fork/join submissions. FIFO. (v0.1 uses one
    /// queue; FJP spreads submissions across several even-slot queues — pending.)
    submissions: VecDeque<Box<dyn FnOnce() + Send>>,
    /// Workers currently executing a task (drives termination detection).
    active: usize,
    /// Panics observed inside tasks (kept observable; no Java handler dispatch yet).
    panics: usize,
    /// shutdown() was called: no new submissions are accepted.
    accepting: bool,
    /// Quiescence reached after shutdown: state is final.
    terminated: bool,
}

struct Shared {
    state: Mutex<PoolState>,
    changed: Condvar,
}

/// Handle mirroring java.util.concurrent.ForkJoinPool (construction + lifecycle only).
pub struct ForkJoinPool {
    shared: Arc<Shared>,
    workers: Vec<thread::JoinHandle<()>>,
    parallelism: usize,
    mode: Mode,
}

impl ForkJoinPool {
    /// Validates exactly like `new ForkJoinPool(parallelism, factory, handler, asyncMode)`
    /// for the two parameters v0.1 models. Other parameters are not modeled yet.
    pub fn new(parallelism: usize, mode: Mode) -> Result<Self, PoolError> {
        validate_parallelism(parallelism)?;
        let shared = Arc::new(Shared {
            state: Mutex::new(PoolState {
                submissions: VecDeque::new(),
                active: 0,
                panics: 0,
                accepting: true,
                terminated: false,
            }),
            changed: Condvar::new(),
        });
        let mut workers = Vec::with_capacity(parallelism);
        for _ in 0..parallelism {
            let shared = Arc::clone(&shared);
            workers.push(thread::spawn(move || worker_loop(shared)));
        }
        Ok(Self { shared, workers, parallelism, mode })
    }

    pub fn parallelism(&self) -> usize {
        self.parallelism
    }
    pub fn mode(&self) -> Mode {
        self.mode
    }

    /// External submission (non-fork/join client). FIFO drain, as in FJP.
    pub fn execute(&self, job: impl FnOnce() + Send + 'static) -> Result<(), PoolError> {
        let mut state = self.shared.state.lock().map_err(|_| PoolError::RejectedExecution)?;
        if !state.accepting {
            return Err(PoolError::RejectedExecution);
        }
        state.submissions.push_back(Box::new(job));
        self.shared.changed.notify_one();
        Ok(())
    }

    pub fn is_shutdown(&self) -> bool {
        self.shared.state.lock().map(|s| !s.accepting).unwrap_or(true)
    }

    /// Non-blocking, like FJP isTerminated(). True only once quiescent post-shutdown.
    pub fn is_terminated(&self) -> bool {
        self.shared.state.lock().map(|s| s.terminated).unwrap_or(true)
    }

    pub fn panic_count(&self) -> usize {
        self.shared.state.lock().map(|s| s.panics).unwrap_or(usize::MAX)
    }

    /// Stops accepting new submissions; queued tasks still run. Mirrors shutdown().
    pub fn shutdown(&self) {
        let mut state = self.shared.state.lock().expect("estado del pool dañado");
        state.accepting = false;
        self.shared.changed.notify_all();
    }

    /// Bounded wait for quiescence after shutdown(). Returns false on timeout.
    pub fn await_termination(&self, timeout: Duration) -> bool {
        let deadline = match Instant::now().checked_add(timeout) {
            Some(d) => d,
            None => return false,
        };
        let mut state = match self.shared.state.lock() {
            Ok(s) => s,
            Err(_) => return true,
        };
        loop {
            if state.terminated {
                return true;
            }
            let now = Instant::now();
            if now >= deadline {
                return false;
            }
            state = match self.shared.changed.wait_timeout(state, deadline - now) {
                Ok((s, _)) => s,
                Err(_) => return true,
            };
        }
    }

    fn stop_and_join(&mut self) {
        {
            let mut state = self.shared.state.lock().expect("estado del pool dañado");
            state.accepting = false;
        }
        self.shared.changed.notify_all();
        for worker in self.workers.drain(..) {
            let _ = worker.join();
        }
    }
}

impl Drop for ForkJoinPool {
    fn drop(&mut self) {
        self.stop_and_join();
    }
}

/// Validates exactly like the ForkJoinPool constructor for parallelism.
/// Extracted so the bounds can be tested without spawning threads.
fn validate_parallelism(parallelism: usize) -> Result<(), PoolError> {
    if parallelism == 0 || parallelism > MAX_PARALLELISM {
        return Err(PoolError::IllegalArgument(format!(
            "parallelism {parallelism} fuera de 1..={MAX_PARALLELISM}"
        )));
    }
    Ok(())
}

fn worker_loop(shared: Arc<Shared>) {
    loop {
        let job = {
            let mut state = shared.state.lock().expect("estado del pool dañado");
            loop {
                if let Some(job) = state.submissions.pop_front() {
                    state.active += 1;
                    break job;
                }
                if !state.accepting && state.active == 0 {
                    state.terminated = true;
                    shared.changed.notify_all();
                    return;
                }
                state = shared.changed.wait(state).expect("estado del pool dañado");
            }
        };
        let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(job)).map_err(|_| {
            shared.state.lock().map(|mut s| s.panics += 1).ok();
        });
        let mut state = shared.state.lock().expect("estado del pool dañado");
        state.active -= 1;
        if !state.accepting && state.active == 0 && state.submissions.is_empty() {
            state.terminated = true;
            shared.changed.notify_all();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn parallelism_bounds_match_java() {
        assert!(matches!(
            validate_parallelism(0),
            Err(PoolError::IllegalArgument(_))
        ));
        assert!(matches!(
            validate_parallelism(MAX_PARALLELISM + 1),
            Err(PoolError::IllegalArgument(_))
        ));
        assert!(validate_parallelism(1).is_ok());
        assert!(validate_parallelism(MAX_PARALLELISM).is_ok());
        assert!(matches!(
            ForkJoinPool::new(0, Mode::Lifo),
            Err(PoolError::IllegalArgument(_))
        ));
        assert!(matches!(
            ForkJoinPool::new(MAX_PARALLELISM + 1, Mode::Lifo),
            Err(PoolError::IllegalArgument(_))
        ));
        assert!(ForkJoinPool::new(4, Mode::Fifo).is_ok());
    }

    #[test]
    fn external_submissions_drain_fifo() {
        let pool = ForkJoinPool::new(1, Mode::Lifo).unwrap();
        let order = Arc::new(Mutex::new(Vec::new()));
        for n in 0..8 {
            let order = Arc::clone(&order);
            pool.execute(move || order.lock().unwrap().push(n)).unwrap();
        }
        pool.shutdown();
        assert!(pool.await_termination(Duration::from_secs(5)));
        assert_eq!(*order.lock().unwrap(), (0..8).collect::<Vec<i32>>());
    }

    #[test]
    fn all_tasks_run_across_workers() {
        let pool = ForkJoinPool::new(4, Mode::Lifo).unwrap();
        let ran = Arc::new(AtomicUsize::new(0));
        for _ in 0..64 {
            let ran = Arc::clone(&ran);
            pool.execute(move || {
                ran.fetch_add(1, Ordering::Relaxed);
            })
            .unwrap();
        }
        pool.shutdown();
        assert!(pool.await_termination(Duration::from_secs(5)));
        assert_eq!(ran.load(Ordering::Relaxed), 64);
    }

    #[test]
    fn submissions_after_shutdown_are_rejected() {
        let pool = ForkJoinPool::new(1, Mode::Lifo).unwrap();
        pool.shutdown();
        assert!(matches!(
            pool.execute(|| {}),
            Err(PoolError::RejectedExecution)
        ));
        assert!(pool.is_shutdown());
        assert!(pool.await_termination(Duration::from_secs(5)));
        assert!(pool.is_terminated());
    }

    #[test]
    fn panicking_task_does_not_kill_pool() {
        let pool = ForkJoinPool::new(2, Mode::Lifo).unwrap();
        pool.execute(|| panic!("boom")).unwrap();
        let ran = Arc::new(AtomicUsize::new(0));
        let ran2 = Arc::clone(&ran);
        pool.execute(move || {
            ran2.fetch_add(1, Ordering::Relaxed);
        })
        .unwrap();
        pool.shutdown();
        assert!(pool.await_termination(Duration::from_secs(5)));
        assert_eq!(ran.load(Ordering::Relaxed), 1);
        assert_eq!(pool.panic_count(), 1);
    }

    #[test]
    fn await_termination_times_out() {
        let pool = ForkJoinPool::new(1, Mode::Lifo).unwrap();
        pool.execute(|| std::thread::sleep(Duration::from_millis(400)))
            .unwrap();
        pool.shutdown();
        assert!(!pool.await_termination(Duration::from_millis(50)));
        assert!(pool.await_termination(Duration::from_secs(5)));
    }
}
