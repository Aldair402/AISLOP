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
use frame_vm::FrameError;
use scheduler::LifecycleHooks;
use std::sync::{Arc, Mutex};
use std::time::Duration;
#[test]
fn await_waits_for_jobs_and_exit_callback_and_reports_failure() {
    use std::sync::mpsc;
    let heap = SharedHeap::default();
    let id = heap
        .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap();
    let ex = Executors::default();
    let (exit_tx, exit_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let release = Arc::new(Mutex::new(release_rx));
    ex.create_with_hooks(
        id,
        1,
        LifecycleHooks {
            factory: Arc::new(|_| Ok("worker".to_owned())),
            on_start: Arc::new(|_| {}),
            on_exit: Arc::new(move |_| {
                exit_tx.send(()).unwrap();
                release.lock().unwrap().recv().unwrap();
                panic!("callback failure");
            }),
        },
    )
    .unwrap();
    let task = ex.submit(&heap, id, || Ok(Value::Void)).unwrap();
    ex.join(task).unwrap();
    ex.shutdown(id).unwrap();
    exit_rx.recv_timeout(Duration::from_secs(2)).unwrap();
    assert!(!ex.await_termination(id, Duration::from_millis(2)).unwrap());
    release_tx.send(()).unwrap();
    assert!(matches!(
        ex.await_termination(id, Duration::from_secs(2)),
        Err(FrameError::Heap("falló callback worker"))
    ));
}
#[test]
fn await_from_own_worker_fails_before_and_after_shutdown() {
    use std::sync::mpsc;
    let heap = SharedHeap::default();
    let id = heap
        .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap();
    let ex = Arc::new(Executors::default());
    ex.create(id, 1).unwrap();
    let (tx, rx) = mpsc::channel();
    let worker_ex = ex.clone();
    ex.execute(id, move || {
        let before = worker_ex.await_termination(id, Duration::from_secs(5));
        worker_ex.shutdown(id)?;
        let after = worker_ex.await_termination(id, Duration::from_secs(5));
        tx.send((before, after)).unwrap();
        Ok(Value::Void)
    })
    .unwrap();
    let (before, after) = rx.recv_timeout(Duration::from_secs(2)).unwrap();
    assert!(matches!(
        before,
        Err(FrameError::Heap(
            "awaitTermination desde worker propio no soportado"
        ))
    ));
    assert!(matches!(
        after,
        Err(FrameError::Heap(
            "awaitTermination desde worker propio no soportado"
        ))
    ));
    assert!(ex.await_termination(id, Duration::from_secs(2)).unwrap());
}
#[test]
fn await_and_shutdown_race_without_start() {
    use std::sync::{mpsc, Barrier};
    for _ in 0..100 {
        let heap = SharedHeap::default();
        let id = heap
            .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
            .unwrap();
        let ex = Arc::new(Executors::default());
        ex.create(id, 1).unwrap();
        assert!(!ex.await_termination(id, Duration::ZERO).unwrap());
        let gate = Arc::new(Barrier::new(2));
        let (tx, rx) = mpsc::channel();
        let e = ex.clone();
        let g = gate.clone();
        let thread = std::thread::spawn(move || {
            g.wait();
            tx.send(e.await_termination(id, Duration::from_secs(2)))
                .unwrap();
        });
        gate.wait();
        ex.shutdown(id).unwrap();
        assert!(rx.recv_timeout(Duration::from_secs(3)).unwrap().unwrap());
        thread.join().unwrap();
    }
}
#[test]
fn lifecycle_callbacks_reject_self_await() {
    use std::sync::mpsc;
    let heap = SharedHeap::default();
    let id = heap
        .allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap();
    let ex = Arc::new(Executors::default());
    let (start_tx, start_rx) = mpsc::channel();
    let (end_tx, end_rx) = mpsc::channel();
    let start_ex = ex.clone();
    let end_ex = ex.clone();
    ex.create_with_hooks(
        id,
        1,
        LifecycleHooks {
            factory: Arc::new(|_| Ok("worker".to_string())),
            on_start: Arc::new(move |_| {
                start_tx
                    .send(start_ex.await_termination(id, Duration::from_secs(5)))
                    .unwrap();
            }),
            on_exit: Arc::new(move |_| {
                end_tx
                    .send(end_ex.await_termination(id, Duration::from_secs(5)))
                    .unwrap();
            }),
        },
    )
    .unwrap();
    let task = ex.submit(&heap, id, || Ok(Value::Void)).unwrap();
    let start = start_rx.recv_timeout(Duration::from_secs(2)).unwrap();
    assert!(matches!(
        start,
        Err(FrameError::Heap(
            "awaitTermination desde worker propio no soportado"
        ))
    ));
    ex.join(task).unwrap();
    ex.shutdown(id).unwrap();
    let end = end_rx.recv_timeout(Duration::from_secs(2)).unwrap();
    assert!(matches!(
        end,
        Err(FrameError::Heap(
            "awaitTermination desde worker propio no soportado"
        ))
    ));
    assert!(ex.await_termination(id, Duration::from_secs(2)).unwrap());
}
