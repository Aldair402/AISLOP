//! Infraestructura Rust para trabajos concurrentes. No implementa ForkJoinPool Java
//! ni comparte todavía el heap JVM experimental con los trabajadores.
use std::collections::VecDeque;
use std::io;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{mpsc, Arc, Condvar, Mutex, Weak};
use std::thread::{self, JoinHandle, ThreadId};

type Job = Box<dyn FnOnce() + Send + 'static>;
thread_local! { static ACTIVE_POOLS: std::cell::RefCell<Vec<usize>> = const { std::cell::RefCell::new(Vec::new()) }; }
struct ActivePool(usize);
impl ActivePool {
    fn enter(shared: &Shared) -> Self {
        let id = shared as *const Shared as usize;
        ACTIVE_POOLS.with(|v| v.borrow_mut().push(id));
        Self(id)
    }
    fn contains(shared: &Shared) -> bool {
        let id = shared as *const Shared as usize;
        ACTIVE_POOLS.with(|v| v.borrow().contains(&id))
    }
}
impl Drop for ActivePool {
    fn drop(&mut self) {
        ACTIVE_POOLS.with(|v| assert_eq!(v.borrow_mut().pop(), Some(self.0)));
    }
}

#[derive(Default)]
struct State {
    jobs: VecDeque<Job>,
    running: usize,
    closed: bool,
    panics: usize,
}

#[derive(Default)]
struct Shared {
    state: Mutex<State>,
    changed: Condvar,
}

/// Cola FIFO con hilos Rust reales; API interna, aún desconectada del bytecode.
/// La implementación monohilo del compilador no usa estas fábricas; la ruta
/// concurrente estándar rechaza el perfil de callbacks reservado a Rayon.
pub struct LifecycleHooks {
    pub factory: Arc<dyn Fn(usize) -> io::Result<String> + Send + Sync>,
    pub on_start: Arc<dyn Fn(usize) + Send + Sync>,
    pub on_exit: Arc<dyn Fn(usize) + Send + Sync>,
}
#[derive(Clone)]
pub struct TerminationHandle;
impl TerminationHandle {
    pub fn wait(&self, _: std::time::Duration) -> Result<Option<usize>, &'static str> {
        Err("terminación concurrente requiere Rayon")
    }
}
pub struct WorkerPool {
    shared: Arc<Shared>,
    workers: Vec<JoinHandle<()>>,
}

pub struct PoolHelper(Weak<Shared>);
impl PoolHelper {
    #[cfg(test)]
    pub fn is_alive(&self) -> bool {
        self.0.upgrade().is_some()
    }
    pub fn is_current(&self) -> bool {
        self.0
            .upgrade()
            .is_some_and(|shared| ActivePool::contains(&shared))
    }
    pub fn help_one(&self) -> bool {
        let Some(shared) = self.0.upgrade() else {
            return false;
        };
        if !ActivePool::contains(&shared) {
            return false;
        }
        let job = {
            let mut state = shared.state.lock().unwrap();
            let job = state.jobs.pop_front();
            if job.is_some() {
                state.running += 1;
            }
            job
        };
        if let Some(job) = job {
            run_job(&shared, job);
            true
        } else {
            false
        }
    }
}
#[derive(Debug, PartialEq, Eq)]
pub enum TaskFailure {
    Panicked,
    Disconnected,
}
pub struct TaskHandle<T> {
    result: mpsc::Receiver<Result<T, TaskFailure>>,
    pool: Arc<Shared>,
}
impl<T> TaskHandle<T> {
    /// Ayuda a ejecutar trabajos pendientes para evitar la inanición por joins
    /// anidados. No implementa prioridades ni el resto de ForkJoinTask Java.
    pub fn get(self) -> Result<T, TaskFailure> {
        loop {
            match self.result.try_recv() {
                Ok(value) => return value,
                Err(mpsc::TryRecvError::Disconnected) => return Err(TaskFailure::Disconnected),
                Err(mpsc::TryRecvError::Empty) => {}
            }
            let mut state = self.pool.state.lock().unwrap();
            // El emisor despierta bajo este mismo mutex, evitando perder la señal.
            match self.result.try_recv() {
                Ok(value) => return value,
                Err(mpsc::TryRecvError::Disconnected) => return Err(TaskFailure::Disconnected),
                Err(mpsc::TryRecvError::Empty) => {}
            }
            if let Some(job) = state.jobs.pop_front() {
                state.running += 1;
                drop(state);
                run_job(&self.pool, job);
            } else {
                drop(self.pool.changed.wait(state).unwrap());
            }
        }
    }
}

impl WorkerPool {
    pub fn new(count: usize) -> io::Result<Self> {
        if count == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "se requiere al menos un trabajador",
            ));
        }
        let shared = Arc::new(Shared::default());
        let mut workers = Vec::with_capacity(count);
        for i in 0..count {
            let s = Arc::clone(&shared);
            match thread::Builder::new()
                .name(format!("mc-aot-worker-{i}"))
                .spawn(move || worker(s))
            {
                Ok(worker) => workers.push(worker),
                Err(e) => {
                    shared.state.lock().unwrap().closed = true;
                    shared.changed.notify_all();
                    for worker in workers {
                        let _ = worker.join();
                    }
                    return Err(e);
                }
            }
        }
        Ok(Self { shared, workers })
    }

    pub fn new_with_hooks(_: usize, _: LifecycleHooks) -> io::Result<Self> {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "callbacks requieren Rayon",
        ))
    }
    pub fn execute(&self, job: impl FnOnce() + Send + 'static) -> Result<(), &'static str> {
        let mut state = self.shared.state.lock().unwrap();
        if state.closed {
            return Err("pool cerrado");
        }
        state.jobs.push_back(Box::new(job));
        self.shared.changed.notify_one();
        Ok(())
    }

    /// Captura un panic como resultado del trabajo; aún no es Java Future.
    pub fn submit<T: Send + 'static>(
        &self,
        job: impl FnOnce() -> T + Send + 'static,
    ) -> Result<TaskHandle<T>, &'static str> {
        let (send, recv) = mpsc::sync_channel(1);
        self.execute(move || {
            let result = catch_unwind(AssertUnwindSafe(job)).map_err(|_| TaskFailure::Panicked);
            let _ = send.send(result);
        })?;
        Ok(TaskHandle {
            result: recv,
            pool: Arc::clone(&self.shared),
        })
    }

    pub fn termination_handle(&self) -> Option<TerminationHandle> {
        None
    }
    pub fn helper(&self) -> PoolHelper {
        PoolHelper(Arc::downgrade(&self.shared))
    }
    pub fn close(&self) {
        let mut state = self.shared.state.lock().unwrap();
        state.closed = true;
        self.shared.changed.notify_all();
    }

    /// No invocar desde un trabajador: podría esperar a su propio trabajo.
    pub fn wait_idle(&self) -> Result<usize, &'static str> {
        if self.is_worker(thread::current().id()) || ActivePool::contains(&self.shared) {
            return Err("espera desde un trabajador");
        }
        let mut state = self.shared.state.lock().unwrap();
        while !state.jobs.is_empty() || state.running != 0 {
            state = self.shared.changed.wait(state).unwrap();
        }
        Ok(state.panics)
    }

    fn is_worker(&self, id: ThreadId) -> bool {
        self.workers.iter().any(|w| w.thread().id() == id)
    }

    pub fn shutdown(mut self) -> Result<usize, &'static str> {
        if self.is_worker(thread::current().id()) || ActivePool::contains(&self.shared) {
            return Err("shutdown desde un trabajador");
        }
        self.close();
        let panics = self.wait_idle()?;
        for worker in self.workers.drain(..) {
            worker.join().map_err(|_| "falló un trabajador")?;
        }
        Ok(panics)
    }
}

impl Drop for WorkerPool {
    fn drop(&mut self) {
        // Avisar y separar los JoinHandle evita deadlock si el último dueño cae
        // dentro de un trabajo. shutdown() es la vía explícita que espera.
        self.close();
    }
}

fn worker(shared: Arc<Shared>) {
    loop {
        let job = {
            let mut state = shared.state.lock().unwrap();
            loop {
                if let Some(job) = state.jobs.pop_front() {
                    state.running += 1;
                    break job;
                }
                if state.closed {
                    return;
                }
                state = shared.changed.wait(state).unwrap();
            }
        };
        run_job(&shared, job);
    }
}

fn run_job(shared: &Shared, job: Job) {
    let failed = catch_unwind(AssertUnwindSafe(|| {
        let _active = ActivePool::enter(shared);
        job();
    }))
    .is_err();
    let mut state = shared.state.lock().unwrap();
    state.running -= 1;
    if failed {
        state.panics += 1;
    }
    shared.changed.notify_all();
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Barrier;

    #[test]
    fn workers_run_concurrently_and_wait_for_all_tasks() {
        let pool = WorkerPool::new(2).unwrap();
        let gate = Arc::new(Barrier::new(3));
        let counter = Arc::new(AtomicUsize::new(0));
        for _ in 0..2 {
            let (gate, counter) = (Arc::clone(&gate), Arc::clone(&counter));
            pool.execute(move || {
                counter.fetch_add(1, Ordering::SeqCst);
                gate.wait();
            })
            .unwrap();
        }
        gate.wait();
        assert_eq!(counter.load(Ordering::SeqCst), 2);
        for _ in 0..1000 {
            let counter = Arc::clone(&counter);
            pool.execute(move || {
                counter.fetch_add(1, Ordering::SeqCst);
            })
            .unwrap();
        }
        assert_eq!(pool.wait_idle(), Ok(0));
        assert_eq!(counter.load(Ordering::SeqCst), 1002);
        assert_eq!(pool.shutdown(), Ok(0));
    }

    #[test]
    fn external_helper_cannot_wait_for_its_own_task() {
        let pool = Arc::new(WorkerPool::new(1).unwrap());
        let (ready_tx, ready_rx) = std::sync::mpsc::channel();
        let (release_tx, release_rx) = std::sync::mpsc::channel();
        pool.execute(move || {
            ready_tx.send(()).unwrap();
            release_rx.recv().unwrap();
        })
        .unwrap();
        ready_rx.recv().unwrap();
        let nested = Arc::clone(&pool);
        let result = pool.submit(move || nested.wait_idle()).unwrap().get();
        assert_eq!(result, Ok(Err("espera desde un trabajador")));
        release_tx.send(()).unwrap();
        assert_eq!(Arc::try_unwrap(pool).ok().unwrap().shutdown(), Ok(0));
    }

    #[test]
    fn nested_join_can_progress_with_one_worker() {
        let pool = Arc::new(WorkerPool::new(1).unwrap());
        let nested_pool = Arc::clone(&pool);
        let parent = pool
            .submit(move || {
                let first = nested_pool.submit(|| 20).unwrap();
                let second = nested_pool.submit(|| 22).unwrap();
                first.get().unwrap() + second.get().unwrap()
            })
            .unwrap();
        assert_eq!(parent.get(), Ok(42));
        assert_eq!(Arc::try_unwrap(pool).ok().unwrap().shutdown(), Ok(0));
    }

    #[test]
    fn submitted_results_and_failures_are_observable() {
        let pool = WorkerPool::new(2).unwrap();
        let result = pool.submit(|| 42usize).unwrap();
        let failure = pool
            .submit(|| -> usize { panic!("fallo controlado") })
            .unwrap();
        assert_eq!(result.get(), Ok(42));
        assert_eq!(failure.get(), Err(TaskFailure::Panicked));
        assert_eq!(pool.shutdown(), Ok(0));
    }

    #[test]
    fn panic_does_not_kill_worker_and_closed_pool_rejects() {
        let pool = WorkerPool::new(1).unwrap();
        let count = Arc::new(AtomicUsize::new(0));
        pool.execute(|| panic!("fallo de prueba")).unwrap();
        let clone = Arc::clone(&count);
        pool.execute(move || {
            clone.fetch_add(1, Ordering::SeqCst);
        })
        .unwrap();
        pool.close();
        assert!(pool.execute(|| {}).is_err());
        assert_eq!(pool.shutdown(), Ok(1));
        assert_eq!(count.load(Ordering::SeqCst), 1);
        assert!(WorkerPool::new(0).is_err());
    }
}
