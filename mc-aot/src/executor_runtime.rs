//! Adaptador interno experimental para submit(Runnable) y join().
//! Sin interrupciones, cancelación, handlers ni excepciones Java generales;
//! las factories Java solo se admiten mediante el perfil restringido del compilador.
use crate::concurrent_heap::{ObjectId, SharedHeap, Value};
use crate::frame_vm::FrameError;
use crate::scheduler::{LifecycleHooks, PoolHelper, TerminationHandle, WorkerPool};
use std::collections::HashMap;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};
type JobResult = Result<Value, FrameError>;
struct Future {
    result: Mutex<Option<JobResult>>,
    changed: Condvar,
    helper: PoolHelper,
}
/// Iniciar Rayon al primer envío, no durante el constructor Java. Rayon aún
/// crea todos sus trabajadores entonces; Java puede crearlos gradualmente.
struct LazyPool {
    count: usize,
    state: Mutex<LazyState>,
    changed: Condvar,
}
#[derive(Default)]
struct LazyState {
    closed: bool,
    pool: Option<Arc<WorkerPool>>,
    hooks: Option<LifecycleHooks>,
    started: bool,
    failed: bool,
    termination: Option<TerminationHandle>,
    helper: Option<PoolHelper>,
}
impl LazyPool {
    fn start(&self) -> Result<Arc<WorkerPool>, FrameError> {
        let mut state = self
            .state
            .lock()
            .map_err(|_| FrameError::Heap("estado del pool dañado"))?;
        if state.closed {
            return Err(FrameError::Heap("pool cerrado"));
        }
        if let Some(pool) = &state.pool {
            return Ok(pool.clone());
        }
        let result = match state.hooks.take() {
            Some(hooks) => WorkerPool::new_with_hooks(self.count, hooks),
            None => WorkerPool::new(self.count),
        };
        let pool = match result {
            Ok(pool) => Arc::new(pool),
            Err(_) => {
                state.closed = true;
                state.failed = true;
                self.changed.notify_all();
                return Err(FrameError::Heap("no se pudo crear pool"));
            }
        };
        state.started = true;
        state.helper = Some(pool.helper());
        state.pool = Some(pool.clone());
        Ok(pool)
    }
    fn close(&self) -> Result<(), FrameError> {
        let mut state = self
            .state
            .lock()
            .map_err(|_| FrameError::Heap("estado del pool dañado"))?;
        state.closed = true;
        state.hooks = None;
        if let Some(pool) = state.pool.take() {
            state.termination = pool.termination_handle();
            state.helper = Some(pool.helper());
            pool.close();
        }
        self.changed.notify_all();
        Ok(())
    }
    fn await_termination(&self, timeout: Duration) -> Result<bool, FrameError> {
        let deadline = Instant::now()
            .checked_add(timeout)
            .ok_or(FrameError::Heap("timeout fuera de rango"))?;
        let mut state = self
            .state
            .lock()
            .map_err(|_| FrameError::Heap("estado del pool dañado"))?;
        if state.helper.as_ref().is_some_and(PoolHelper::is_current) {
            return Err(FrameError::Heap(
                "awaitTermination desde worker propio no soportado",
            ));
        }
        while !state.closed {
            let now = Instant::now();
            if now >= deadline {
                return Ok(false);
            }
            let (next, _) = self
                .changed
                .wait_timeout(state, deadline.saturating_duration_since(now))
                .map_err(|_| FrameError::Heap("estado del pool dañado"))?;
            state = next;
        }
        if state.failed {
            return Err(FrameError::Heap("no se pudo crear pool"));
        }
        if !state.started {
            return Ok(true);
        }
        let handle = state
            .termination
            .clone()
            .ok_or(FrameError::Heap("terminación real requiere Rayon"))?;
        drop(state);
        match handle
            .wait(deadline.saturating_duration_since(Instant::now()))
            .map_err(FrameError::Heap)?
        {
            Some(0) => Ok(true),
            Some(_) => Err(FrameError::Heap("falló callback worker")),
            None => Ok(false),
        }
    }
}
#[derive(Default)]
struct Pools {
    live: HashMap<ObjectId, Arc<LazyPool>>,
    closed: HashMap<ObjectId, Arc<LazyPool>>,
}
#[derive(Default)]
pub struct Executors {
    pools: Mutex<Pools>,
    futures: Mutex<HashMap<ObjectId, Arc<Future>>>,
}
impl Executors {
    pub fn create(&self, id: ObjectId, count: i32) -> Result<(), FrameError> {
        self.create_internal(id, count, None)
    }
    pub fn create_with_hooks(
        &self,
        id: ObjectId,
        count: i32,
        hooks: LifecycleHooks,
    ) -> Result<(), FrameError> {
        self.create_internal(id, count, Some(hooks))
    }
    fn create_internal(
        &self,
        id: ObjectId,
        count: i32,
        hooks: Option<LifecycleHooks>,
    ) -> Result<(), FrameError> {
        if !(1..=255).contains(&count) {
            return Err(FrameError::Heap("paralelismo fuera del perfil 1..255"));
        }
        let mut pools = self
            .pools
            .lock()
            .map_err(|_| FrameError::Heap("registro de pools dañado"))?;
        if pools.live.contains_key(&id) || pools.closed.contains_key(&id) {
            return Err(FrameError::Heap("pool ya inicializado"));
        }
        pools.live.insert(
            id,
            Arc::new(LazyPool {
                count: count as usize,
                state: Mutex::new(LazyState {
                    closed: false,
                    pool: None,
                    hooks,
                    ..LazyState::default()
                }),
                changed: Condvar::new(),
            }),
        );
        Ok(())
    }
    fn pool(&self, id: ObjectId) -> Result<Arc<WorkerPool>, FrameError> {
        let lazy = {
            let pools = self
                .pools
                .lock()
                .map_err(|_| FrameError::Heap("registro de pools dañado"))?;
            pools.live.get(&id).cloned().ok_or(FrameError::Heap(
                if pools.closed.contains_key(&id) {
                    "pool cerrado"
                } else {
                    "pool no inicializado"
                },
            ))?
        };
        lazy.start()
    }
    pub fn submit(
        &self,
        heap: &SharedHeap,
        id: ObjectId,
        task: impl FnOnce() -> JobResult + Send + 'static,
    ) -> Result<ObjectId, FrameError> {
        let pool = self.pool(id)?;
        let reference = heap.allocate_typed("java/util/concurrent/ForkJoinTask", vec![])?;
        let future = Arc::new(Future {
            result: Mutex::new(None),
            changed: Condvar::new(),
            helper: pool.helper(),
        });
        let callback = future.clone();
        pool.execute(move || {
            let result = catch_unwind(AssertUnwindSafe(task))
                .map_err(|_| FrameError::Heap("falló tarea nativa"))
                .and_then(|v| v);
            *callback.result.lock().unwrap() = Some(result);
            callback.changed.notify_all();
        })
        .map_err(|_| FrameError::Heap("submit rechazado"))?;
        self.futures
            .lock()
            .map_err(|_| FrameError::Heap("registro de tareas dañado"))?
            .insert(reference, future);
        Ok(reference)
    }
    /// execute sin Future: una tarea que falla termina el proceso de forma
    /// diagnóstica; no se suplanta el handler ni se fabrican Throwable Java.
    pub fn execute(
        &self,
        id: ObjectId,
        task: impl FnOnce() -> JobResult + Send + 'static,
    ) -> Result<(), FrameError> {
        let pool = self.pool(id)?;
        pool.execute(move || {
            let result = catch_unwind(AssertUnwindSafe(task))
                .map_err(|_| FrameError::Heap("falló tarea nativa"))
                .and_then(|v| v);
            if !matches!(result, Ok(Value::Void)) {
                eprintln!("execute Runnable falló; excepciones Java no soportadas: {result:?}");
                std::process::exit(2);
            }
        })
        .map_err(|_| FrameError::Heap("execute rechazado"))?;
        Ok(())
    }
    pub fn join(&self, id: ObjectId) -> Result<(), FrameError> {
        let future = self
            .futures
            .lock()
            .map_err(|_| FrameError::Heap("registro de tareas dañado"))?
            .get(&id)
            .cloned()
            .ok_or(FrameError::Heap("tarea inexistente"))?;
        loop {
            let state = future
                .result
                .lock()
                .map_err(|_| FrameError::Heap("estado de tarea dañado"))?;
            if let Some(result) = state.as_ref() {
                return match result {
                    Ok(Value::Void) => Ok(()),
                    Ok(_) => Err(FrameError::Heap("Runnable devolvió valor")),
                    Err(e) => Err(e.clone()),
                };
            }
            drop(state);
            if future.helper.help_one() {
                continue;
            }
            let state = future
                .result
                .lock()
                .map_err(|_| FrameError::Heap("estado de tarea dañado"))?;
            if state.is_none() {
                let _ = future
                    .changed
                    .wait_timeout(state, Duration::from_millis(1))
                    .map_err(|_| FrameError::Heap("estado de tarea dañado"))?;
            }
        }
    }
    pub fn await_termination(&self, id: ObjectId, timeout: Duration) -> Result<bool, FrameError> {
        let pool = {
            let pools = self
                .pools
                .lock()
                .map_err(|_| FrameError::Heap("registro de pools dañado"))?;
            pools
                .live
                .get(&id)
                .or_else(|| pools.closed.get(&id))
                .cloned()
                .ok_or(FrameError::Heap("pool no inicializado"))?
        };
        pool.await_termination(timeout)
    }
    pub fn shutdown(&self, id: ObjectId) -> Result<(), FrameError> {
        let pool = {
            let mut pools = self
                .pools
                .lock()
                .map_err(|_| FrameError::Heap("registro de pools dañado"))?;
            if pools.closed.contains_key(&id) {
                return Ok(());
            }
            let pool = pools
                .live
                .remove(&id)
                .ok_or(FrameError::Heap("pool no inicializado"))?;
            pools.closed.insert(id, pool.clone());
            pool
        };
        pool.close()?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejected_hooks_never_fall_back_to_default_pool() {
        let heap = SharedHeap::default();
        let id = heap
            .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
            .unwrap();
        let ex = Executors::default();
        let hooks = LifecycleHooks {
            factory: Arc::new(|_| Err(std::io::Error::other("factory falló"))),
            on_start: Arc::new(|_| {}),
            on_exit: Arc::new(|_| {}),
        };
        ex.create_with_hooks(id, 1, hooks).unwrap();
        assert!(matches!(
            ex.pool(id),
            Err(FrameError::Heap("no se pudo crear pool"))
        ));
        assert!(matches!(ex.pool(id), Err(FrameError::Heap("pool cerrado"))));
        assert!(matches!(
            ex.await_termination(id, Duration::ZERO),
            Err(FrameError::Heap("no se pudo crear pool"))
        ));
    }
    #[test]
    fn racing_first_use_creates_only_one_pool() {
        let heap = SharedHeap::default();
        let id = heap
            .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
            .unwrap();
        let ex = Arc::new(Executors::default());
        ex.create(id, 2).unwrap();
        let gate = Arc::new(std::sync::Barrier::new(9));
        let threads = (0..8)
            .map(|_| {
                let ex = ex.clone();
                let gate = gate.clone();
                std::thread::spawn(move || {
                    gate.wait();
                    ex.pool(id).unwrap()
                })
            })
            .collect::<Vec<_>>();
        gate.wait();
        let pools = threads
            .into_iter()
            .map(|t| t.join().unwrap())
            .collect::<Vec<_>>();
        assert!(pools.iter().all(|p| Arc::ptr_eq(p, &pools[0])));
        drop(pools);
        ex.shutdown(id).unwrap();
    }
    #[test]
    fn constructor_and_unused_shutdown_do_not_start_workers() {
        let heap = SharedHeap::default();
        let id = heap
            .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
            .unwrap();
        let executors = Executors::default();
        executors.create(id, 1).unwrap();
        let lazy = executors
            .pools
            .lock()
            .unwrap()
            .live
            .get(&id)
            .unwrap()
            .clone();
        assert!(lazy.state.lock().unwrap().pool.is_none());
        executors.shutdown(id).unwrap();
        let state = lazy.state.lock().unwrap();
        assert!(state.closed);
        assert!(state.pool.is_none());
    }
    #[test]
    fn completed_future_does_not_keep_shutdown_pool_alive() {
        let heap = SharedHeap::default();
        let pool = heap
            .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
            .unwrap();
        let executors = Executors::default();
        executors.create(pool, 1).unwrap();
        let task = executors.submit(&heap, pool, || Ok(Value::Void)).unwrap();
        executors.join(task).unwrap();
        executors.shutdown(pool).unwrap();
        let future = executors
            .futures
            .lock()
            .unwrap()
            .get(&task)
            .unwrap()
            .clone();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while future.helper.is_alive() && std::time::Instant::now() < deadline {
            std::thread::yield_now();
        }
        assert!(!future.helper.is_alive());
        assert!(executors.join(task).is_ok());
    }
}
