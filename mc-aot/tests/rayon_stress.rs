//! B-08: repeticiones de invariantes concurrentes sobre trabajadores Rayon reales.
//! No compara órdenes que Java no garantiza ni implementa ForkJoinPool completo.
//! Cada prueba corre bajo un perro guardián: si el cuerpo no termina en el plazo,
//! el fallo es «posible bloqueo» y no un test colgado.
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
use scheduler::WorkerPool;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{mpsc::RecvTimeoutError, Arc, Barrier, Mutex};
use std::time::Duration;

/// Ejecuta el cuerpo en otro hilo y falla si no termina en el plazo, para
/// distinguir un bloqueo de un panic normal del cuerpo.
fn con_guardián(nombre: &'static str, plazo: Duration, cuerpo: impl FnOnce() + Send + 'static) {
    let (tx, rx) = std::sync::mpsc::channel();
    let hilo = std::thread::spawn(move || {
        cuerpo();
        let _ = tx.send(());
    });
    match rx.recv_timeout(plazo) {
        Ok(()) => hilo.join().expect("el cuerpo del estrés hizo panic"),
        Err(RecvTimeoutError::Timeout) => {
            panic!("{nombre}: posible bloqueo, el cuerpo no terminó en {plazo:?}")
        }
        Err(RecvTimeoutError::Disconnected) => {
            hilo.join().expect("el cuerpo del estrés hizo panic");
        }
    }
}

fn pool_object(heap: &SharedHeap) -> ObjectId {
    heap.allocate_typed("java/util/concurrent/ForkJoinPool", vec![])
        .unwrap()
}

/// Publicación, alias, monitor reentrante y RMW atómico en 20 rondas.
/// El invariante es el total exacto, no el orden de las operaciones.
#[test]
fn monitor_alias_and_rmw_repeat() {
    con_guardián(
        "monitor_alias_and_rmw_repeat",
        Duration::from_secs(180),
        || {
            for ronda in 0..20 {
                let heap = SharedHeap::default();
                let compartido = heap.allocate(vec![Value::Int(0)]).unwrap();
                let alias = compartido;
                let contador = heap.allocate(vec![Value::Int(0)]).unwrap();
                let pool = WorkerPool::new(4).unwrap();
                let puerta = Arc::new(Barrier::new(5));
                for _ in 0..4 {
                    let (h, g) = (heap.clone(), Arc::clone(&puerta));
                    pool.execute(move || {
                        g.wait();
                        for _ in 0..500 {
                            let _exterior = h.enter(compartido).unwrap();
                            let _interior = h.enter(compartido).unwrap();
                            let Value::Int(v) = h.read(alias, 0).unwrap() else {
                                panic!("tipo de campo inesperado")
                            };
                            h.write(alias, 0, Value::Int(v + 1)).unwrap();
                            let _ = h.get_and_add_int(contador, 0, 1).unwrap();
                        }
                    })
                    .unwrap();
                }
                puerta.wait();
                assert_eq!(pool.shutdown(), Ok(0), "ronda {ronda}: falló el cierre");
                assert_eq!(
                    heap.read(compartido, 0),
                    Ok(Value::Int(2000)),
                    "ronda {ronda}: incrementos bajo monitor"
                );
                assert_eq!(
                    heap.read(contador, 0),
                    Ok(Value::Int(2000)),
                    "ronda {ronda}: incrementos atómicos"
                );
            }
        },
    );
}

/// Publicación de un objeto en un «estático» antes de liberar a los trabajadores,
/// y lectura concurrente del mismo alias. Se repite para detectar carreras de
/// publicación que una sola pasada podría no revelar.
#[test]
fn publication_then_concurrent_reads_repeat() {
    con_guardián(
        "publication_then_concurrent_reads_repeat",
        Duration::from_secs(120),
        || {
            for ronda in 0..20 {
                let heap = SharedHeap::default();
                let estaticos = heap.allocate(vec![Value::Ref(None)]).unwrap();
                let objeto = heap.allocate(vec![Value::Int(41)]).unwrap();
                heap.write(estaticos, 0, Value::Ref(Some(objeto))).unwrap();
                let pool = WorkerPool::new(4).unwrap();
                let puerta = Arc::new(Barrier::new(5));
                for _ in 0..4 {
                    let (h, g, est) = (heap.clone(), Arc::clone(&puerta), estaticos);
                    pool.execute(move || {
                        g.wait();
                        for _ in 0..250 {
                            let Value::Ref(Some(publicado)) = h.read(est, 0).unwrap() else {
                                panic!("publicación no visible")
                            };
                            let Value::Int(v) = h.read(publicado, 0).unwrap() else {
                                panic!("campo publicado de tipo inesperado")
                            };
                            if v != 41 {
                                panic!("valor publicado alterado: {v}");
                            }
                        }
                    })
                    .unwrap();
                }
                puerta.wait();
                assert_eq!(pool.shutdown(), Ok(0), "ronda {ronda}");
            }
        },
    );
}

/// Carreras de finalización: varios envíos y varios `join` concurrentes sobre las
/// mismas tareas, más cierre posterior. Invariantes: todo `join` termina bien, el
/// contador es exacto y no queda ninguna tarea colgada.
#[test]
fn completion_races_repeat() {
    con_guardián("completion_races_repeat", Duration::from_secs(180), || {
        for ronda in 0..20 {
            let heap = SharedHeap::default();
            let ex = Arc::new(Executors::default());
            let pool = pool_object(&heap);
            ex.create(pool, 4).unwrap();
            let contador = heap.allocate(vec![Value::Int(0)]).unwrap();
            let mut tareas = Vec::new();
            for _ in 0..8 {
                let (h, c) = (heap.clone(), contador);
                tareas.push(
                    ex.submit(&heap, pool, move || {
                        let _ = h.get_and_add_int(c, 0, 1).unwrap();
                        Ok(Value::Void)
                    })
                    .unwrap(),
                );
            }
            let mut hilos = Vec::new();
            for _ in 0..3 {
                let (ex, tareas) = (Arc::clone(&ex), tareas.clone());
                hilos.push(std::thread::spawn(move || {
                    for tarea in tareas {
                        ex.join(tarea).expect("join concurrente falló");
                        ex.join(tarea).expect("join repetido falló");
                    }
                }));
            }
            for hilo in hilos {
                hilo.join().expect("hilo de join falló");
            }
            assert_eq!(
                heap.read(contador, 0),
                Ok(Value::Int(8)),
                "ronda {ronda}: finalización única"
            );
            ex.shutdown(pool).unwrap();
            assert_eq!(ex.is_shutdown(pool), Ok(true), "ronda {ronda}");
        }
    });
}

/// Carrera entre envíos y cierre: cada intento debe aceptarse (y su `join`
/// terminar) o rechazarse con error; nunca bloquearse ni perder una tarea
/// aceptada. Se repite para cubrir intercalados distintos.
#[test]
fn close_race_keeps_every_task_or_rejects_it() {
    con_guardián(
        "close_race_keeps_every_task_or_rejects_it",
        Duration::from_secs(180),
        || {
            for ronda in 0..30 {
                let heap = SharedHeap::default();
                let ex = Arc::new(Executors::default());
                let pool = pool_object(&heap);
                ex.create(pool, 2).unwrap();
                let aceptadas = Arc::new(Mutex::new(Vec::new()));
                let rechazadas = Arc::new(AtomicUsize::new(0));
                let intentos = 16;
                let productor = {
                    let (ex, h, aceptadas, rechazadas) =
                        (Arc::clone(&ex), heap.clone(), Arc::clone(&aceptadas), Arc::clone(&rechazadas));
                    std::thread::spawn(move || {
                        for _ in 0..intentos {
                            match ex.submit(&h, pool, || Ok(Value::Void)) {
                                Ok(tarea) => aceptadas.lock().unwrap().push(tarea),
                                Err(_) => {
                                    rechazadas.fetch_add(1, Ordering::SeqCst);
                                }
                            }
                        }
                    })
                };
                ex.shutdown(pool).unwrap();
                productor.join().expect("productor falló");
                let tareas = aceptadas.lock().unwrap().clone();
                for tarea in &tareas {
                    ex.join(*tarea).expect("una tarea aceptada no terminó");
                }
                assert_eq!(
                    tareas.len() + rechazadas.load(Ordering::SeqCst),
                    intentos,
                    "ronda {ronda}: se perdió un intento"
                );
                assert_eq!(ex.is_shutdown(pool), Ok(true), "ronda {ronda}");
                // Cerrar otra vez es idempotente y no resucita el pool.
                ex.shutdown(pool).unwrap();
                assert!(
                    ex.submit(&heap, pool, || Ok(Value::Void)).is_err(),
                    "ronda {ronda}: el pool cerrado aceptó trabajo"
                );
            }
        },
    );
}

/// Carrera de finalización de un futuro pendiente: muchos `complete` concurrentes
/// y exactamente un ganador. Invariante de identidad y de finalización única.
#[test]
fn pending_future_completion_race_has_single_winner() {
    con_guardián(
        "pending_future_completion_race_has_single_winner",
        Duration::from_secs(120),
        || {
            for ronda in 0..20 {
                let heap = SharedHeap::default();
                let futuro = heap
                    .allocate_typed("java/util/concurrent/CompletableFuture", vec![])
                    .unwrap();
                heap.mark_pending_future(futuro).unwrap();
                let valor = heap.intern_string(&[b'o' as u16, b'k' as u16]).unwrap();
                let ganadores = Arc::new(AtomicUsize::new(0));
                let pool = WorkerPool::new(4).unwrap();
                let puerta = Arc::new(Barrier::new(5));
                for _ in 0..4 {
                    let (h, g, w) = (heap.clone(), Arc::clone(&puerta), Arc::clone(&ganadores));
                    pool.execute(move || {
                        g.wait();
                        for _ in 0..50 {
                            if h.future_complete(futuro, Some(valor)).unwrap() {
                                w.fetch_add(1, Ordering::SeqCst);
                            }
                        }
                    })
                    .unwrap();
                }
                puerta.wait();
                assert_eq!(pool.shutdown(), Ok(0), "ronda {ronda}");
                assert_eq!(
                    ganadores.load(Ordering::SeqCst),
                    1,
                    "ronda {ronda}: más de un `complete` devolvió true"
                );
                assert_eq!(
                    heap.completed_future_value(futuro),
                    Ok(Some(valor)),
                    "ronda {ronda}: valor publicado"
                );
            }
        },
    );
}

/// B-09: reenlazado de una cadena de referencias bajo monitor desde varios workers.
/// Invariantes: ningún nodo se pierde ni se duplica, cada valor sigue intacto y la
/// cadena recorrida desde la cabeza alcanza exactamente todos los nodos (sin ciclos).
/// No se compara orden de escritura, solo el resultado final.
#[test]
fn relink_under_monitor_keeps_the_chain_whole() {
    con_guardián(
        "relink_under_monitor_keeps_the_chain_whole",
        Duration::from_secs(120),
        || {
            const NODOS: usize = 64;
            for ronda in 0..20 {
                let heap = SharedHeap::default();
                let nodos: Vec<ObjectId> = (0..NODOS)
                    .map(|i| {
                        heap.allocate(vec![Value::Int(i as i32), Value::Ref(None)])
                            .unwrap()
                    })
                    .collect();
                for par in nodos.windows(2) {
                    heap.write(par[0], 1, Value::Ref(Some(par[1]))).unwrap();
                }
                let pool = WorkerPool::new(4).unwrap();
                let puerta = Arc::new(Barrier::new(5));
                for hilo in 0..4usize {
                    let (h, g, ns) = (heap.clone(), Arc::clone(&puerta), nodos.clone());
                    pool.execute(move || {
                        g.wait();
                        for intento in 0..100usize {
                            let indice = (hilo * 16 + intento) % ns.len();
                            // Regla acordada con A: monitor del objeto y, dentro, la
                            // operacion del heap (su mutex es hoja). Nunca al reves.
                            let guardia = h.enter(ns[indice]).unwrap();
                            if let Ok(Value::Ref(Some(siguiente))) = h.read(ns[indice], 1) {
                                let destino = ns[(indice + 1) % ns.len()];
                                h.write(ns[indice], 1, Value::Ref(Some(destino))).unwrap();
                                std::hint::black_box(siguiente);
                            }
                            drop(guardia);
                        }
                    })
                    .unwrap();
                }
                puerta.wait();
                assert_eq!(pool.shutdown(), Ok(0), "ronda {ronda}");
                for (i, nodo) in nodos.iter().enumerate() {
                    assert_eq!(
                        heap.read(*nodo, 0),
                        Ok(Value::Int(i as i32)),
                        "ronda {ronda}: valor del nodo {i} alterado"
                    );
                    assert!(
                        matches!(heap.read(*nodo, 1), Ok(Value::Ref(_))),
                        "ronda {ronda}: el campo de referencia quedo en un valor inesperado"
                    );
                }
                let mut recorridos = 0usize;
                let mut actual = Some(nodos[0]);
                while let Some(id) = actual {
                    recorridos += 1;
                    assert!(
                        recorridos <= NODOS,
                        "ronda {ronda}: la cadena tiene un ciclo"
                    );
                    actual = match heap.read(id, 1).unwrap() {
                        Value::Ref(siguiente) => siguiente,
                        otro => panic!("ronda {ronda}: campo de referencia no valido: {otro:?}"),
                    };
                }
                assert_eq!(
                    recorridos, NODOS,
                    "ronda {ronda}: la cadena alcanza {recorridos} de {NODOS} nodos"
                );
            }
        },
    );
}
