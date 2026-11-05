//! B-07: frontera estable para el frente A. Verifica el contrato de uso del
//! adaptador concurrente: creación, envío, espera, cierre, transporte de
//! referencias y rechazos. No implementa ForkJoinPool completo ni excepciones
//! Java: cada límite se comprueba como rechazo explícito.
#![allow(dead_code)]
#[path = "../src/concurrent_heap.rs"]
mod concurrent_heap;
#[path = "../src/executor_runtime.rs"]
mod executor_runtime;
#[path = "../src/frame_vm.rs"]
mod frame_vm;
#[path = "../src/rayon_scheduler.rs"]
mod scheduler;
use concurrent_heap::{ObjectId, SharedHeap, Value};
use executor_runtime::Executors;
use frame_vm::FrameError;
use std::sync::{mpsc, Arc};
use std::time::Duration;

fn pool(heap: &SharedHeap) -> ObjectId {
    heap.allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap()
}

/// 1. Creación: el paralelismo admitido es 1..=255 y un pool no se registra dos veces.
#[test]
fn create_accepts_only_the_declared_parallelism() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    for count in [1, 2, 255] {
        let id = pool(&heap);
        assert!(ex.create(id, count).is_ok(), "paralelismo {count} rechazado");
        assert_eq!(ex.parallelism(id), Ok(count));
    }
    for count in [0, -1, 256] {
        let id = pool(&heap);
        assert_eq!(
            ex.create(id, count),
            Err(FrameError::Heap("paralelismo fuera del perfil 1..255"))
        );
    }
    let id = pool(&heap);
    ex.create(id, 2).unwrap();
    assert_eq!(ex.create(id, 2), Err(FrameError::Heap("pool ya inicializado")));
}

/// 2. Envío y espera: identificadores distintos, `join` idempotente y sin fugas
///    hacia objetos que no son tareas de este registro.
#[test]
fn submit_and_join_are_idempotent_and_scoped() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&heap);
    ex.create(id, 2).unwrap();
    let contador = heap.allocate(vec![Value::Int(0)]).unwrap();
    let mut tareas = Vec::new();
    for _ in 0..4 {
        let (h, c) = (heap.clone(), contador);
        tareas.push(
            ex.submit(&heap, id, move || {
                let _ = h.get_and_add_int(c, 0, 1).unwrap();
                Ok(Value::Void)
            })
            .unwrap(),
        );
    }
    assert_eq!(
        tareas.iter().collect::<std::collections::HashSet<_>>().len(),
        4,
        "cada tarea debe tener identidad propia"
    );
    for tarea in &tareas {
        ex.join(*tarea).expect("primer join");
        ex.join(*tarea).expect("join repetido");
    }
    assert_eq!(heap.read(contador, 0), Ok(Value::Int(4)));
    // Un objeto que no es una tarea del registro no se puede esperar.
    let ajeno = heap.allocate(vec![Value::Int(0)]).unwrap();
    assert_eq!(ex.join(ajeno), Err(FrameError::Heap("tarea inexistente")));
}

/// 3. Esperas: solo desde el llamador. Un worker que intenta esperar el cierre de
///    su propio pool recibe un rechazo, no un bloqueo silencioso.
#[test]
fn await_termination_is_callers_only() {
    let heap = SharedHeap::default();
    let ex = Arc::new(Executors::default());
    let id = pool(&heap);
    ex.create(id, 2).unwrap();
    let (tx, rx) = mpsc::channel();
    let (ex_tarea, heap_tarea) = (Arc::clone(&ex), heap.clone());
    let tarea = ex
        .submit(&heap, id, move || {
            let resultado = ex_tarea.await_termination(id, Duration::from_millis(1));
            let _ = tx.send(format!("{resultado:?}"));
            Ok(Value::Void)
        })
        .unwrap();
    ex.join(tarea).unwrap();
    let observado = rx.recv_timeout(Duration::from_secs(5)).expect("sin respuesta");
    assert!(
        observado.contains("awaitTermination desde worker propio no soportado"),
        "un worker no debe poder esperar su propio cierre: {observado}"
    );
    let _ = heap_tarea;
    // Desde el llamador, tras el cierre, la espera sí termina.
    ex.shutdown(id).unwrap();
    assert!(matches!(
        ex.await_termination(id, Duration::from_secs(5)),
        Ok(true) | Err(FrameError::Heap("terminación real requiere Rayon"))
    ));
}

/// 4. Cierre: idempotente, rechaza envíos posteriores y no resucita.
#[test]
fn close_is_idempotent_and_final() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&heap);
    ex.create(id, 1).unwrap();
    ex.shutdown(id).unwrap();
    ex.shutdown(id).unwrap();
    assert_eq!(ex.is_shutdown(id), Ok(true));
    assert!(ex.submit(&heap, id, || Ok(Value::Void)).is_err());
    assert_eq!(ex.parallelism(id), Ok(1), "el paralelismo se conserva");
}

/// 5. Transporte de referencias: un futuro pendiente publicado en un campo del
///    heap lo completa un worker y el llamador ve el valor. Es el caso que A
///    necesita para publicar objetos entre el backend principal y las tareas.
#[test]
fn pending_future_published_to_a_worker_is_visible() {
    let heap = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&heap);
    ex.create(id, 1).unwrap();
    let objeto = heap.allocate(vec![Value::Int(7)]).unwrap();
    let futuro = heap
        .allocate_typed("java/util/concurrent/CompletableFuture", vec![])
        .unwrap();
    heap.mark_pending_future(futuro).unwrap();
    let publicador = heap.allocate(vec![Value::Ref(Some(futuro))]).unwrap();
    let (h, objetivo, valor) = (heap.clone(), futuro, objeto);
    let tarea = ex
        .submit(&heap, id, move || {
            let Value::Ref(Some(pendiente)) = h.read(publicador, 0).unwrap() else {
                return Err(FrameError::Heap("publicación perdida"));
            };
            if pendiente != objetivo {
                return Err(FrameError::Heap("identidad de futuro distinta"));
            }
            if !h.future_complete(pendiente, Some(valor)).unwrap() {
                return Err(FrameError::Heap("complete duplicado"));
            }
            Ok(Value::Void)
        })
        .unwrap();
    ex.join(tarea).unwrap();
    assert_eq!(heap.future_is_done(futuro), Ok(true));
    assert_eq!(heap.completed_future_value(futuro), Ok(Some(objeto)));
    assert_eq!(heap.read(objeto, 0), Ok(Value::Int(7)));
}

/// 6. Pertenencia: ids y valores de otro heap se rechazan en vez de mezclarse.
#[test]
fn foreign_heap_references_are_rejected() {
    let heap = SharedHeap::default();
    let otro = SharedHeap::default();
    let ex = Executors::default();
    let id = pool(&heap);
    ex.create(id, 1).unwrap();
    let ajeno = otro.allocate(vec![Value::Int(1)]).unwrap();
    assert_eq!(ex.parallelism(ajeno), Err(FrameError::Heap("pool no inicializado")));
    assert_eq!(ex.is_shutdown(ajeno), Err(FrameError::Heap("pool no inicializado")));
    let futuro = heap
        .allocate_typed("java/util/concurrent/CompletableFuture", vec![])
        .unwrap();
    heap.mark_pending_future(futuro).unwrap();
    assert!(heap.future_complete(futuro, Some(ajeno)).is_err(), "valor de otro heap");
}
