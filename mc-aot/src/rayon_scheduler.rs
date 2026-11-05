//! Adaptador experimental de un executor con work stealing. NO es todavía
//! java.util.concurrent.ForkJoinPool completo; los hooks Java restringidos
//! se conectan por executor_runtime/frame_vm, no por este módulo aislado.
use rayon::{ThreadPool, ThreadPoolBuilder};
use std::cell::RefCell;
use std::io;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{mpsc, Arc, Condvar, Mutex, Weak};
use std::time::{Duration, Instant};

thread_local! {static ACTIVE:RefCell<Vec<usize>>=const {RefCell::new(Vec::new())};}
thread_local! {static LIFECYCLE_ACTIVE:RefCell<Vec<usize>>=const {RefCell::new(Vec::new())};}
struct ActiveLifecycle(usize);
impl ActiveLifecycle {
    fn enter(tracker: &LifeTracker) -> Self {
        let id = tracker as *const LifeTracker as usize;
        LIFECYCLE_ACTIVE.with(|x| x.borrow_mut().push(id));
        Self(id)
    }
    fn contains(tracker: &LifeTracker) -> bool {
        let id = tracker as *const LifeTracker as usize;
        LIFECYCLE_ACTIVE.with(|x| x.borrow().contains(&id))
    }
}
impl Drop for ActiveLifecycle {
    fn drop(&mut self) {
        LIFECYCLE_ACTIVE.with(|x| assert_eq!(x.borrow_mut().pop(), Some(self.0)));
    }
}
struct Active(usize);
impl Active {
    fn enter(inner: &Inner) -> Self {
        let id = inner as *const Inner as usize;
        ACTIVE.with(|x| x.borrow_mut().push(id));
        Self(id)
    }
    fn contains(inner: &Inner) -> bool {
        let id = inner as *const Inner as usize;
        ACTIVE.with(|x| x.borrow().contains(&id))
    }
}
impl Drop for Active {
    fn drop(&mut self) {
        ACTIVE.with(|x| assert_eq!(x.borrow_mut().pop(), Some(self.0)));
    }
}
#[derive(Default)]
struct State {
    closed: bool,
    pending: usize,
    panics: usize,
}
/// Hooks Rust de infraestructura. No son callbacks Java y no implementan
/// el comportamiento de fallos de ForkJoinWorkerThread.
pub struct LifecycleHooks {
    pub factory: Arc<dyn Fn(usize) -> io::Result<String> + Send + Sync>,
    pub on_start: Arc<dyn Fn(usize) + Send + Sync>,
    pub on_exit: Arc<dyn Fn(usize) + Send + Sync>,
}
#[derive(Default)]
struct LifeState {
    active: usize,
    callback_panics: usize,
}
#[derive(Default)]
struct LifeTracker {
    state: Mutex<LifeState>,
    changed: Condvar,
}
/// Contador independiente del pool: no mantiene el pool ni los hilos vivos.
#[derive(Clone)]
pub struct TerminationHandle(Arc<LifeTracker>);
impl TerminationHandle {
    /// None significa timeout. Some(n) son los callbacks Rust que hicieron panic.
    pub fn wait(&self, timeout: Duration) -> Result<Option<usize>, &'static str> {
        let deadline = Instant::now()
            .checked_add(timeout)
            .ok_or("timeout fuera de rango")?;
        let mut state = self
            .0
            .state
            .lock()
            .map_err(|_| "estado de terminación dañado")?;
        while state.active != 0 {
            let now = Instant::now();
            if now >= deadline {
                return Ok(None);
            }
            let (next, _) = self
                .0
                .changed
                .wait_timeout(state, deadline.saturating_duration_since(now))
                .map_err(|_| "estado de terminación dañado")?;
            state = next;
        }
        Ok(Some(state.callback_panics))
    }
}
struct Inner {
    pool: ThreadPool,
    state: Mutex<State>,
    changed: Condvar,
    termination: Option<TerminationHandle>,
}
pub struct WorkerPool {
    inner: Arc<Inner>,
}
pub struct PoolHelper(Weak<Inner>, Weak<LifeTracker>);
impl PoolHelper {
    #[cfg(test)]
    pub fn is_alive(&self) -> bool {
        self.0.upgrade().is_some()
    }
    pub fn is_current(&self) -> bool {
        self.1
            .upgrade()
            .is_some_and(|tracker| ActiveLifecycle::contains(&tracker))
            || self
                .0
                .upgrade()
                .is_some_and(|inner| Active::contains(&inner))
    }
    pub fn help_one(&self) -> bool {
        self.0
            .upgrade()
            .is_some_and(|inner| Active::contains(&inner) && rayon::yield_now().is_some())
    }
}
#[derive(Debug, PartialEq, Eq)]
pub enum TaskFailure {
    Panicked,
    Disconnected,
}
pub struct TaskHandle<T> {
    receiver: mpsc::Receiver<Result<T, TaskFailure>>,
    inner: Arc<Inner>,
}
impl<T> TaskHandle<T> {
    /// Un trabajador ayuda a la cola antes de bloquear; desde fuera solo espera.
    pub fn get(self) -> Result<T, TaskFailure> {
        loop {
            match self.receiver.try_recv() {
                Ok(v) => return v,
                Err(mpsc::TryRecvError::Disconnected) => return Err(TaskFailure::Disconnected),
                Err(mpsc::TryRecvError::Empty) => {}
            }
            if Active::contains(&self.inner) && rayon::yield_now().is_some() {
                continue;
            }
            match self.receiver.recv_timeout(Duration::from_millis(1)) {
                Ok(v) => return v,
                Err(mpsc::RecvTimeoutError::Disconnected) => return Err(TaskFailure::Disconnected),
                Err(mpsc::RecvTimeoutError::Timeout) => {}
            }
        }
    }
}
impl WorkerPool {
    pub fn new(count: usize) -> io::Result<Self> {
        Self::new_with_hooks(
            count,
            LifecycleHooks {
                factory: Arc::new(|i| Ok(format!("mc-aot-rayon-{i}"))),
                on_start: Arc::new(|_| {}),
                on_exit: Arc::new(|_| {}),
            },
        )
    }
    /// Fábrica y eventos de vida en Rust para preparar futuros callbacks Java.
    /// Rayon solicita todos los hilos al construir el pool: no es el protocolo
    /// ni la inicialización diferida de ForkJoinPool.
    pub fn new_with_hooks(count: usize, hooks: LifecycleHooks) -> io::Result<Self> {
        if count == 0 || count > 32767 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "paralelismo fuera de rango",
            ));
        }
        let tracker = Arc::new(LifeTracker::default());
        let handler_tracker = tracker.clone();
        let pool = ThreadPoolBuilder::new()
            .num_threads(count)
            .spawn_handler(move |worker| {
                let index = worker.index();
                let name = catch_unwind(AssertUnwindSafe(|| (hooks.factory)(index)))
                    .map_err(|_| io::Error::other("panic en fábrica Rust"))??;
                let on_start = hooks.on_start.clone();
                let on_exit = hooks.on_exit.clone();
                let tracker = handler_tracker.clone();
                {
                    let mut state = tracker.state.lock().unwrap();
                    state.active += 1;
                }
                let done = tracker.clone();
                match std::thread::Builder::new().name(name).spawn(move || {
                    let _active_lifecycle = ActiveLifecycle::enter(&tracker);
                    let mut failures = 0;
                    if catch_unwind(AssertUnwindSafe(|| on_start(index))).is_err() {
                        failures += 1;
                    }
                    if catch_unwind(AssertUnwindSafe(|| worker.run())).is_err() {
                        failures += 1;
                    }
                    if catch_unwind(AssertUnwindSafe(|| on_exit(index))).is_err() {
                        failures += 1;
                    }
                    let mut state = tracker.state.lock().unwrap();
                    state.callback_panics += failures;
                    state.active -= 1;
                    tracker.changed.notify_all();
                }) {
                    Ok(_) => Ok(()),
                    Err(e) => {
                        let mut state = done.state.lock().unwrap();
                        state.active -= 1;
                        done.changed.notify_all();
                        Err(e)
                    }
                }
            })
            .build()
            .map_err(io::Error::other)?;
        Ok(Self {
            inner: Arc::new(Inner {
                pool,
                state: Mutex::new(State::default()),
                changed: Condvar::new(),
                termination: Some(TerminationHandle(tracker)),
            }),
        })
    }
    pub fn termination_handle(&self) -> Option<TerminationHandle> {
        self.inner.termination.clone()
    }
    pub fn execute(&self, job: impl FnOnce() + Send + 'static) -> Result<(), &'static str> {
        let mut state = self
            .inner
            .state
            .lock()
            .map_err(|_| "estado del executor dañado")?;
        if state.closed {
            return Err("pool cerrado");
        }
        state.pending = state.pending.checked_add(1).ok_or("demasiadas tareas")?;
        let inner = Arc::clone(&self.inner);
        // asyncMode=true en Minecraft: prioridad FIFO local, no garantía global.
        self.inner.pool.spawn_fifo(move || {
            let failed = catch_unwind(AssertUnwindSafe(|| {
                let _active = Active::enter(&inner);
                job();
            }))
            .is_err();
            let mut state = inner.state.lock().unwrap();
            state.pending -= 1;
            if failed {
                state.panics += 1;
            }
            inner.changed.notify_all();
        });
        Ok(())
    }
    pub fn submit<T: Send + 'static>(
        &self,
        job: impl FnOnce() -> T + Send + 'static,
    ) -> Result<TaskHandle<T>, &'static str> {
        let (tx, receiver) = mpsc::sync_channel(1);
        self.execute(move || {
            let result = catch_unwind(AssertUnwindSafe(job)).map_err(|_| TaskFailure::Panicked);
            let _ = tx.send(result);
        })?;
        Ok(TaskHandle {
            receiver,
            inner: Arc::clone(&self.inner),
        })
    }
    pub fn helper(&self) -> PoolHelper {
        PoolHelper(
            Arc::downgrade(&self.inner),
            self.inner
                .termination
                .as_ref()
                .map(|t| Arc::downgrade(&t.0))
                .unwrap_or_default(),
        )
    }
    pub fn close(&self) {
        let mut state = self.inner.state.lock().unwrap();
        state.closed = true;
        self.inner.changed.notify_all();
    }
    pub fn wait_idle(&self) -> Result<usize, &'static str> {
        if Active::contains(&self.inner) {
            return Err("espera desde un trabajador");
        }
        let mut state = self.inner.state.lock().unwrap();
        while state.pending != 0 {
            state = self.inner.changed.wait(state).unwrap();
        }
        Ok(state.panics)
    }
    /// Solo espera cierre y ausencia de trabajos. No demuestra terminación
    /// de hilos Java y no debe usarse como implementación de awaitTermination.
    pub fn await_closed_idle(&self, timeout: Duration) -> Result<bool, &'static str> {
        if Active::contains(&self.inner) {
            return Err("espera desde un trabajador");
        }
        let deadline = Instant::now()
            .checked_add(timeout)
            .ok_or("timeout fuera de rango")?;
        let mut state = self.inner.state.lock().unwrap();
        loop {
            if state.closed && state.pending == 0 {
                return Ok(true);
            }
            let now = Instant::now();
            if now >= deadline {
                return Ok(false);
            }
            let (s, _) = self
                .inner
                .changed
                .wait_timeout(state, deadline.saturating_duration_since(now))
                .unwrap();
            state = s;
        }
    }
    pub fn shutdown(self) -> Result<usize, &'static str> {
        if Active::contains(&self.inner) {
            return Err("shutdown desde un trabajador");
        }
        self.close();
        self.wait_idle()
    }
}
impl Drop for WorkerPool {
    fn drop(&mut self) {
        self.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{
        atomic::{AtomicUsize, Ordering},
        Barrier,
    };
    #[test]
    fn factory_start_exit_and_real_thread_termination() {
        let events = Arc::new(Mutex::new(Vec::new()));
        let a = events.clone();
        let b = events.clone();
        let c = events.clone();
        let hooks = LifecycleHooks {
            factory: Arc::new(move |i| {
                a.lock().unwrap().push((i, "factory"));
                Ok(format!("fixture-{i}"))
            }),
            on_start: Arc::new(move |i| {
                assert_eq!(
                    std::thread::current().name(),
                    Some(format!("fixture-{i}").as_str())
                );
                b.lock().unwrap().push((i, "start"));
            }),
            on_exit: Arc::new(move |i| {
                c.lock().unwrap().push((i, "exit"));
            }),
        };
        let pool = WorkerPool::new_with_hooks(3, hooks).unwrap();
        let done = pool.termination_handle().unwrap();
        let barrier = Arc::new(Barrier::new(4));
        for _ in 0..3 {
            let b = barrier.clone();
            pool.execute(move || {
                b.wait();
            })
            .unwrap();
        }
        barrier.wait();
        pool.close();
        assert_eq!(done.wait(Duration::from_millis(10)).unwrap(), None);
        pool.shutdown().unwrap();
        assert_eq!(done.wait(Duration::from_secs(2)).unwrap(), Some(0));
        let events = events.lock().unwrap();
        for i in 0..3 {
            let seq = events
                .iter()
                .filter_map(|(j, e)| (*j == i).then_some(*e))
                .collect::<Vec<_>>();
            assert_eq!(seq, ["factory", "start", "exit"]);
        }
    }
    #[test]
    fn rust_factory_error_does_not_create_a_pool() {
        let hooks = LifecycleHooks {
            factory: Arc::new(|_| Err(io::Error::other("rechazada"))),
            on_start: Arc::new(|_| {}),
            on_exit: Arc::new(|_| {}),
        };
        assert!(WorkerPool::new_with_hooks(1, hooks).is_err());
    }
    #[test]
    fn hook_failure_is_reported_not_discarded() {
        let hooks = LifecycleHooks {
            factory: Arc::new(|_| Ok("hook-failure".into())),
            on_start: Arc::new(|_| panic!("hook")),
            on_exit: Arc::new(|_| {}),
        };
        let pool = WorkerPool::new_with_hooks(1, hooks).unwrap();
        let done = pool.termination_handle().unwrap();
        pool.shutdown().unwrap();
        assert_eq!(done.wait(Duration::from_secs(2)).unwrap(), Some(1));
    }
    #[test]
    fn parallel_and_shared() {
        let p = WorkerPool::new(4).unwrap();
        let n = Arc::new(AtomicUsize::new(0));
        let b = Arc::new(Barrier::new(5));
        for _ in 0..4 {
            let (n, b) = (n.clone(), b.clone());
            p.execute(move || {
                n.fetch_add(1, Ordering::SeqCst);
                b.wait();
            })
            .unwrap();
        }
        b.wait();
        assert_eq!(n.load(Ordering::SeqCst), 4);
        assert_eq!(p.shutdown(), Ok(0));
    }
    #[test]
    fn one_worker_helps_nested_join() {
        let p = Arc::new(WorkerPool::new(1).unwrap());
        let q = p.clone();
        let h = p
            .submit(move || {
                let child = q.submit(|| 41).unwrap();
                child.get().unwrap() + 1
            })
            .unwrap();
        assert_eq!(h.get(), Ok(42));
        assert_eq!(p.wait_idle(), Ok(0));
        assert!(Arc::try_unwrap(p).ok().unwrap().shutdown().is_ok());
    }
    #[test]
    fn shutdown_timeout_rejection_and_panic() {
        let p = WorkerPool::new(2).unwrap();
        assert!(!p.await_closed_idle(Duration::from_millis(1)).unwrap());
        let gate = Arc::new(Barrier::new(2));
        let g = gate.clone();
        p.execute(move || {
            g.wait();
        })
        .unwrap();
        p.close();
        assert_eq!(p.execute(|| {}), Err("pool cerrado"));
        assert!(!p.await_closed_idle(Duration::from_millis(10)).unwrap());
        gate.wait();
        assert!(p.await_closed_idle(Duration::from_secs(2)).unwrap());
        assert_eq!(p.shutdown(), Ok(0));
        let p = WorkerPool::new(1).unwrap();
        let h = p.submit(|| panic!("fallo")).unwrap();
        assert_eq!(h.get(), Err(TaskFailure::Panicked));
        assert_eq!(p.shutdown(), Ok(0));
    }
    #[test]
    fn weak_helper_does_not_keep_closed_pool_alive() {
        let pool = WorkerPool::new(1).unwrap();
        let helper = pool.helper();
        assert_eq!(pool.submit(|| 42).unwrap().get(), Ok(42));
        pool.shutdown().unwrap();
        let deadline = std::time::Instant::now() + Duration::from_secs(2);
        while helper.0.upgrade().is_some() && std::time::Instant::now() < deadline {
            std::thread::yield_now();
        }
        assert!(
            helper.0.upgrade().is_none(),
            "helper no debe retener el pool"
        );
    }
    #[test]
    fn reject_invalid_parallelism() {
        assert!(WorkerPool::new(0).is_err());
        assert!(WorkerPool::new(32768).is_err());
    }
}
