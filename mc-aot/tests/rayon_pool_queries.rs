//! Consultas de lifecycle del perfil restringido sobre trabajadores Rayon reales.
//! No implementan ForkJoinPool completo ni excepciones Java.
#![allow(dead_code)]
#[path = "../src/concurrent_heap.rs"]
mod concurrent_heap;
#[path = "../src/executor_runtime.rs"]
mod executor_runtime;
#[path = "../src/frame_vm.rs"]
mod frame_vm;
#[path = "../src/rayon_scheduler.rs"]
mod scheduler;
use concurrent_heap::{SharedHeap, Value};
use executor_runtime::Executors;
use std::time::{Duration, Instant};

fn pool(ex: &Executors, heap: &SharedHeap, count: i32) -> concurrent_heap::ObjectId {
    let id = heap
        .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap();
    ex.create(id, count).unwrap();
    id
}

fn wait_terminated(ex: &Executors, id: concurrent_heap::ObjectId, limit: Duration) -> bool {
    let deadline = Instant::now() + limit;
    while Instant::now() < deadline {
        match ex.is_terminated(id) {
            Ok(true) => return true,
            Ok(false) => std::thread::sleep(Duration::from_millis(1)),
            Err(e) => panic!("is_terminated falló: {e:?}"),
        }
    }
    false
}

#[test]
fn queries_track_real_worker_lifecycle() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&ex, &heap, 2);
    assert_eq!(ex.is_shutdown(id), Ok(false));
    assert_eq!(ex.is_terminated(id), Ok(false));
    assert_eq!(ex.parallelism(id), Ok(2));
    let task = ex.submit(&heap, id, || Ok(Value::Void)).unwrap();
    ex.join(task).unwrap();
    assert_eq!(ex.is_shutdown(id), Ok(false));
    ex.shutdown(id).unwrap();
    assert_eq!(ex.is_shutdown(id), Ok(true));
    assert_eq!(ex.parallelism(id), Ok(2));
    assert!(
        wait_terminated(&ex, id, Duration::from_secs(5)),
        "el pool no terminó tras el cierre"
    );
}

#[test]
fn unused_pool_terminates_immediately_after_shutdown() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&ex, &heap, 3);
    ex.shutdown(id).unwrap();
    // Java: un pool que nunca se usó queda terminado al cerrarse.
    assert_eq!(ex.is_shutdown(id), Ok(true));
    assert_eq!(ex.is_terminated(id), Ok(true));
    assert_eq!(ex.parallelism(id), Ok(3));
}

#[test]
fn running_task_keeps_pool_not_terminated() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&ex, &heap, 1);
    let task = ex
        .submit(&heap, id, || {
            std::thread::sleep(Duration::from_millis(300));
            Ok(Value::Void)
        })
        .unwrap();
    let started = Instant::now();
    ex.shutdown(id).unwrap();
    assert_eq!(ex.is_shutdown(id), Ok(true));
    assert!(
        matches!(ex.is_terminated(id), Ok(false)),
        "Java: isTerminated() es false mientras hay una tarea en curso"
    );
    assert!(
        started.elapsed() < Duration::from_millis(250),
        "Java: shutdown() no espera a las tareas en curso; tardó {:?}",
        started.elapsed()
    );
    ex.join(task).unwrap();
    assert!(wait_terminated(&ex, id, Duration::from_secs(5)));
}

#[test]
fn foreign_pool_ids_are_rejected_not_answered() {
    let other = SharedHeap::default();
    let ex = Executors::default();
    let foreign = other
        .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap();
    assert!(ex.is_shutdown(foreign).is_err());
    assert!(ex.is_terminated(foreign).is_err());
    assert!(ex.parallelism(foreign).is_err());
}
