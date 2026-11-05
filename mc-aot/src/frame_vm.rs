//! Experimento de frames reanudables para código Rust generado.
//! El backend concurrent-int-demo genera funciones con este formato;
//! solo admite un subconjunto y todavía no modela excepciones Java.
use crate::concurrent_heap::{MonitorGuard, ObjectId, SharedHeap, Value};
use crate::executor_runtime::Executors;
use crate::scheduler::LifecycleHooks;
use std::collections::HashMap;
use std::sync::Arc;
use std::sync::Mutex;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameError {
    Heap(&'static str),
    StackUnderflow,
    InvalidMethod,
    FrameLimit,
    StepLimit,
}
impl From<&'static str> for FrameError {
    fn from(value: &'static str) -> Self {
        Self::Heap(value)
    }
}
pub struct Frame {
    pub pc: usize,
    pub locals: Vec<Value>,
    stack: Vec<Value>,
    _monitor: Option<MonitorGuard>,
}
impl Frame {
    pub fn push(&mut self, value: Value) {
        self.stack.push(value);
    }
    pub fn pop(&mut self) -> Result<Value, FrameError> {
        self.stack.pop().ok_or(FrameError::StackUnderflow)
    }
}
pub enum Step {
    Continue,
    Call {
        method: usize,
        args: Vec<Value>,
    },
    Return(Value),
    ReturnVoid,
    PoolCreate {
        pool: ObjectId,
        count: i32,
    },
    PoolCreateCustom {
        pool: ObjectId,
        count: i32,
        factory: ObjectId,
        capture: Option<Vec<Value>>,
        create: usize,
        worker: &'static str,
        start: usize,
        end: usize,
        statics: Value,
    },
    PoolSubmit {
        pool: ObjectId,
        method: usize,
        args: Vec<Value>,
    },
    PoolAwait {
        pool: ObjectId,
        nanos: u64,
    },
    PoolExecute {
        pool: ObjectId,
        method: usize,
        args: Vec<Value>,
    },
    TaskJoin {
        task: ObjectId,
    },
    PoolShutdown {
        pool: ObjectId,
    },
    PoolIsShutdown {
        pool: ObjectId,
    },
    PoolIsTerminated {
        pool: ObjectId,
    },
    PoolParallelism {
        pool: ObjectId,
    },
}
pub type NativeStep = fn(&SharedHeap, &mut Frame) -> Result<Step, FrameError>;
#[derive(Clone)]
pub struct Program {
    methods: Vec<NativeStep>,
    synchronized: Vec<u8>,
    local_counts: Option<Vec<usize>>,
}
impl Program {
    pub fn new(methods: Vec<NativeStep>) -> Self {
        let synchronized = vec![0; methods.len()];
        Self {
            methods,
            synchronized,
            local_counts: None,
        }
    }
    pub fn with_monitors(methods: Vec<NativeStep>, synchronized: Vec<u8>) -> Self {
        assert_eq!(methods.len(), synchronized.len());
        Self {
            methods,
            synchronized,
            local_counts: None,
        }
    }
    pub fn with_layouts(
        methods: Vec<NativeStep>,
        synchronized: Vec<u8>,
        local_counts: Vec<usize>,
    ) -> Self {
        assert_eq!(methods.len(), local_counts.len());
        let mut p = Self::with_monitors(methods, synchronized);
        p.local_counts = Some(local_counts);
        p
    }
    fn frame(
        &self,
        heap: &SharedHeap,
        method: usize,
        mut args: Vec<Value>,
    ) -> Result<Frame, FrameError> {
        let flag = *self
            .synchronized
            .get(method)
            .ok_or(FrameError::InvalidMethod)?;
        let monitor = if flag != 0 {
            let target = if flag == 1 {
                args.last()
            } else if flag == 2 {
                args.first()
            } else {
                return Err(FrameError::InvalidMethod);
            };
            let Some(Value::Ref(Some(id))) = target else {
                return Err(FrameError::Heap("monitor estático ausente"));
            };
            Some(heap.enter(*id)?)
        } else {
            None
        };
        if let Some(layouts) = &self.local_counts {
            let slots = *layouts.get(method).ok_or(FrameError::InvalidMethod)?;
            let statics = args.pop().ok_or(FrameError::Heap("estáticos ausentes"))?;
            let mut expanded = Vec::with_capacity(args.len());
            for arg in args {
                expanded.push(arg);
                if matches!(arg, Value::Long(_)) {
                    expanded.push(Value::Void);
                }
            }
            args = expanded;
            if args.len() > slots {
                return Err(FrameError::Heap("locales insuficientes"));
            }
            args.resize(slots, Value::Void);
            args.push(statics);
        }
        Ok(Frame {
            pc: 0,
            locals: args,
            stack: Vec::new(),
            _monitor: monitor,
        })
    }
    /// Cada ejecución tiene su pila privada; los accesos al heap se bloquean
    /// por operación. Llamadas/retornos aún no modelan excepciones Java.
    pub fn run(
        &self,
        heap: &SharedHeap,
        method: usize,
        args: Vec<Value>,
        limit: usize,
    ) -> Result<Value, FrameError> {
        self.run_with_executors(heap, method, args, limit, None)
    }
    pub fn run_with_executors(
        &self,
        heap: &SharedHeap,
        method: usize,
        args: Vec<Value>,
        limit: usize,
        executors: Option<Arc<Executors>>,
    ) -> Result<Value, FrameError> {
        if method >= self.methods.len() {
            return Err(FrameError::InvalidMethod);
        }
        let mut frames = vec![(method, self.frame(heap, method, args)?)];
        for _ in 0..limit {
            let (method, frame) = frames.last_mut().expect("frame inicial");
            match (self.methods[*method])(heap, frame)? {
                Step::Continue => {}
                Step::Call { method, args } => {
                    if method >= self.methods.len() {
                        return Err(FrameError::InvalidMethod);
                    }
                    if frames.len() >= 256 {
                        return Err(FrameError::FrameLimit);
                    }
                    frames.push((method, self.frame(heap, method, args)?));
                }
                Step::PoolCreate { pool, count } => {
                    executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .create(pool, count)?;
                }
                Step::PoolCreateCustom {
                    pool,
                    count,
                    factory,
                    capture,
                    create,
                    worker,
                    start,
                    end,
                    statics,
                } => {
                    let context = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .clone();
                    let workers = Arc::new(Mutex::new(HashMap::<usize, ObjectId>::new()));
                    let (h, p, c, w) =
                        (heap.clone(), self.clone(), context.clone(), workers.clone());
                    let factory_hook = Arc::new(move |index: usize| -> std::io::Result<String> {
                        let mut args = capture
                            .clone()
                            .unwrap_or_else(|| vec![Value::Ref(Some(factory))]);
                        args.push(Value::Ref(Some(pool)));
                        args.push(statics);
                        let result = p.run_with_executors(&h, create, args, limit, Some(c.clone()));
                        let id = match result {
                            Ok(Value::Ref(Some(id))) if h.class_of(id) == Ok(Some(worker)) => id,
                            other => {
                                return Err(std::io::Error::other(format!(
                                    "factory Java no soportada: {other:?}"
                                )))
                            }
                        };
                        w.lock()
                            .map_err(|_| std::io::Error::other("registro worker dañado"))?
                            .insert(index, id);
                        h.worker_os_name(id)
                            .map_err(std::io::Error::other)
                            .map(|name| {
                                name.unwrap_or_else(|| format!("mc-aot-java-worker-{index}"))
                            })
                    });
                    let (h, p, c, w) =
                        (heap.clone(), self.clone(), context.clone(), workers.clone());
                    let start_hook = Arc::new(move |index: usize| {
                        let id = *w
                            .lock()
                            .expect("registro worker dañado")
                            .get(&index)
                            .expect("worker sin factory");
                        let result = p.run_with_executors(
                            &h,
                            start,
                            vec![Value::Ref(Some(id)), statics],
                            limit,
                            Some(c.clone()),
                        );
                        if !matches!(result, Ok(Value::Void)) {
                            eprintln!("onStart Java falló; excepciones no soportadas: {result:?}");
                            std::process::exit(2);
                        }
                    });
                    let (h, p, c, w) =
                        (heap.clone(), self.clone(), context.clone(), workers.clone());
                    let exit_hook = Arc::new(move |index: usize| {
                        let id = *w
                            .lock()
                            .expect("registro worker dañado")
                            .get(&index)
                            .expect("worker sin factory");
                        let result = p.run_with_executors(
                            &h,
                            end,
                            vec![Value::Ref(Some(id)), Value::Ref(None), statics],
                            limit,
                            Some(c.clone()),
                        );
                        if !matches!(result, Ok(Value::Void)) {
                            eprintln!(
                                "onTermination Java falló; excepciones no soportadas: {result:?}"
                            );
                            std::process::exit(2);
                        }
                    });
                    context.create_with_hooks(
                        pool,
                        count,
                        LifecycleHooks {
                            factory: factory_hook,
                            on_start: start_hook,
                            on_exit: exit_hook,
                        },
                    )?;
                }
                Step::PoolShutdown { pool } => {
                    executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .shutdown(pool)?;
                }
                Step::PoolIsShutdown { pool } => {
                    let closed = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .is_shutdown(pool)?;
                    frame.push(Value::Int(i32::from(closed)));
                }
                Step::PoolIsTerminated { pool } => {
                    let terminated = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .is_terminated(pool)?;
                    frame.push(Value::Int(i32::from(terminated)));
                }
                Step::PoolParallelism { pool } => {
                    let parallelism = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .parallelism(pool)?;
                    frame.push(Value::Int(parallelism));
                }
                Step::PoolSubmit { pool, method, args } => {
                    let context = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .clone();
                    let task_context = context.clone();
                    let program = self.clone();
                    let shared = heap.clone();
                    let task = context.submit(heap, pool, move || {
                        program.run_with_executors(&shared, method, args, limit, Some(task_context))
                    })?;
                    frame.push(Value::Ref(Some(task)));
                }
                Step::PoolAwait { pool, nanos } => {
                    let done = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .await_termination(pool, std::time::Duration::from_nanos(nanos))?;
                    frame.push(Value::Int(i32::from(done)));
                }
                Step::PoolExecute { pool, method, args } => {
                    let context = executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .clone();
                    let task_context = context.clone();
                    let program = self.clone();
                    let shared = heap.clone();
                    context.execute(pool, move || {
                        program.run_with_executors(&shared, method, args, limit, Some(task_context))
                    })?;
                }
                Step::TaskJoin { task } => {
                    executors
                        .as_ref()
                        .ok_or(FrameError::Heap("adaptador executor no disponible"))?
                        .join(task)?;
                    frame.push(Value::Ref(None));
                }
                Step::ReturnVoid => {
                    frames.pop();
                    if frames.is_empty() {
                        return Ok(Value::Void);
                    }
                }
                Step::Return(value) => {
                    frames.pop();
                    if let Some((_, caller)) = frames.last_mut() {
                        caller.push(value);
                    } else {
                        return Ok(value);
                    }
                }
            }
        }
        Err(FrameError::StepLimit)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::scheduler::WorkerPool;
    use std::sync::{Arc, Barrier};
    // Estas funciones imitan la salida AOT por PC, no traducen bytecode real.
    fn entry(_: &SharedHeap, f: &mut Frame) -> Result<Step, FrameError> {
        match f.pc {
            0 => {
                f.pc = 1;
                Ok(Step::Call {
                    method: 1,
                    args: f.locals.clone(),
                })
            }
            1 => Ok(Step::Return(f.pop()?)),
            _ => Err(FrameError::InvalidMethod),
        }
    }
    fn increment(heap: &SharedHeap, f: &mut Frame) -> Result<Step, FrameError> {
        let Value::Ref(Some(id)) = f.locals[0] else {
            return Err(FrameError::Heap("referencia inválida"));
        };
        match f.pc {
            0 => {
                let old = heap.read(id, 0)?;
                f.push(old);
                f.pc = 1;
                Ok(Step::Continue)
            }
            1 => {
                let Value::Int(old) = f.pop()? else {
                    return Err(FrameError::Heap("tipo"));
                };
                if heap.compare_exchange(id, 0, Value::Int(old), Value::Int(old.wrapping_add(1)))? {
                    Ok(Step::Return(Value::Int(old)))
                } else {
                    f.pc = 0;
                    Ok(Step::Continue)
                }
            }
            _ => Err(FrameError::InvalidMethod),
        }
    }
    fn forever(_: &SharedHeap, _: &mut Frame) -> Result<Step, FrameError> {
        Ok(Step::Continue)
    }
    #[test]
    fn synchronized_frame_releases_monitor_on_step_error() {
        let heap = SharedHeap::default();
        let id = heap.allocate(vec![]).unwrap();
        let program = Program::with_monitors(vec![forever], vec![1]);
        assert_eq!(
            program.run(&heap, 0, vec![Value::Ref(Some(id))], 3),
            Err(FrameError::StepLimit)
        );
        let h = heap.clone();
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let _guard = h.enter(id).unwrap();
            tx.send(()).unwrap();
        });
        assert!(rx.recv_timeout(std::time::Duration::from_secs(2)).is_ok());
    }

    #[test]
    fn worker_frames_share_heap_without_sharing_operand_stacks() {
        let heap = SharedHeap::default();
        let id = heap.allocate(vec![Value::Int(0)]).unwrap();
        let program = Arc::new(Program::new(vec![entry, increment]));
        let start = Arc::new(Barrier::new(5));
        let pool = WorkerPool::new(4).unwrap();
        for _ in 0..4 {
            let (h, p, b) = (heap.clone(), program.clone(), start.clone());
            pool.execute(move || {
                b.wait();
                for _ in 0..500 {
                    p.run(&h, 0, vec![Value::Ref(Some(id))], 100_000).unwrap();
                }
            })
            .unwrap();
        }
        start.wait();
        assert_eq!(pool.shutdown(), Ok(0));
        assert_eq!(heap.read(id, 0), Ok(Value::Int(2000)));
        assert_eq!(
            program.run(&heap, 5, vec![], 1),
            Err(FrameError::InvalidMethod)
        );
        assert_eq!(
            program.run(&heap, 0, vec![Value::Ref(Some(id))], 1),
            Err(FrameError::StepLimit)
        );
    }
}
