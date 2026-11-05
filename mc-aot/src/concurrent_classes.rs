//! Ensayo de registro de clases y estáticos sobre el heap compartido.
//! No está conectado a la resolución ni al bytecode del backend generado.
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::class_init::{ClassInit, InitError};
use crate::concurrent_heap::{ObjectId, SharedHeap, Value};

pub struct RuntimeClass {
    init: ClassInit,
    statics: ObjectId,
}
impl RuntimeClass {
    /// El inicializador es responsable de preparar las dependencias Java antes
    /// de escribir campos; las excepciones Java no están modeladas todavía.
    pub fn ensure(&self, f: impl FnOnce(ObjectId) -> Result<(), ()>) -> Result<(), InitError> {
        self.init.ensure(|| f(self.statics))
    }
    pub fn statics(&self) -> ObjectId {
        self.statics
    }
}
#[derive(Default)]
pub struct ConcurrentClasses {
    heap: SharedHeap,
    classes: Mutex<HashMap<String, Arc<RuntimeClass>>>,
}
impl ConcurrentClasses {
    pub fn heap(&self) -> SharedHeap {
        self.heap.clone()
    }
    /// Un solo espacio de nombres; no representa ClassLoaders ni su identidad.
    pub fn register(
        &self,
        name: &str,
        fields: Vec<Value>,
    ) -> Result<Arc<RuntimeClass>, &'static str> {
        let mut classes = self.classes.lock().map_err(|_| "registro dañado")?;
        if classes.contains_key(name) {
            return Err("clase duplicada");
        }
        let statics = self.heap.allocate(fields)?;
        let class = Arc::new(RuntimeClass {
            init: ClassInit::default(),
            statics,
        });
        classes.insert(name.to_owned(), Arc::clone(&class));
        Ok(class)
    }
    pub fn get(&self, name: &str) -> Option<Arc<RuntimeClass>> {
        self.classes.lock().ok()?.get(name).cloned()
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::scheduler::WorkerPool;
    use std::sync::{
        atomic::{AtomicUsize, Ordering},
        Barrier,
    };

    #[test]
    fn initialized_statics_are_published_to_waiting_workers() {
        let classes = Arc::new(ConcurrentClasses::default());
        let class = classes.register("Example", vec![Value::Int(0)]).unwrap();
        assert!(classes.register("Example", vec![]).is_err());
        assert!(Arc::ptr_eq(&class, &classes.get("Example").unwrap()));
        let count = Arc::new(AtomicUsize::new(0));
        let barrier = Arc::new(Barrier::new(5));
        let pool = WorkerPool::new(4).unwrap();
        for _ in 0..4 {
            let (c, h, count, b) = (
                class.clone(),
                classes.heap(),
                count.clone(),
                barrier.clone(),
            );
            pool.execute(move || {
                b.wait();
                c.ensure(|id| {
                    count.fetch_add(1, Ordering::SeqCst);
                    h.write(id, 0, Value::Int(42)).unwrap();
                    Ok(())
                })
                .unwrap();
                assert_eq!(h.read(c.statics(), 0), Ok(Value::Int(42)));
            })
            .unwrap();
        }
        barrier.wait();
        assert_eq!(pool.shutdown(), Ok(0));
        assert_eq!(count.load(Ordering::SeqCst), 1);
    }
}
