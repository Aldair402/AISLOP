# Contrato B-01 — `ForkJoinPool`, workers, lifecycle y futuros

**Tarea:** B-01 de [`TODO.md`](../TODO.md) · **Base:** commit `8fa1893` · **Fecha:** 2026-11-05
**Responsable propuesto:** quien tome B-01 · **Revisión cruzada:** frentes A y C
**Estado:** contrato redactado y verificado por máquina; **no** cierra B-01 hasta que C integre las entradas de la suite y alguien revise la matriz.

---

## 1. Qué es y qué no es este documento

Partimos de los dos oráculos Java existentes y los convertimos en un **contrato comprobable**: una lista de casos donde cada uno declara si su semántica está

- fijada solo en Java (**oráculo**),
- comparada contra el backend nativo (**diferencial**),
- rechazada por el nativo con un mensaje concreto (**guarda**),
- probada solo a nivel Rust (**unitaria**), o
- simplemente **no modelada** (falta).

Esto **no** afirma equivalencia con Java, ni que `ForkJoinPool` esté implementado, ni que `Main` arranque. Un rechazo no es equivalencia: significa que el adaptador se niega a seguir en lugar de inventar comportamiento. Tampoco certifica ninguna clase completa.

La pareja `analysis/futures-contract-b01.json` (matriz legible por máquina) y `mc-aot/tests/check-futures-contract.py` (verificador) son la parte ejecutable del contrato; este `.md` es la parte legible. **Los dos se comprueban mutuamente** para que no se desincronicen.

## 2. Cómo se comprueba (y qué no)

```sh
python3 mc-aot/tests/check-futures-contract.py            # valida el contrato
python3 mc-aot/tests/check-futures-contract.py --summary  # imprime la matriz caso a caso
```

El verificador **no ejecuta Java ni el backend nativo**. Lo que sí exige, sobre el repositorio:

1. Todo caso con estado *diferencial* cita un test que **existe** y que está en `mc-aot/run-regressions.sh`.
2. Todo mensaje de guarda citado aparece **literalmente** en `mc-aot/src` (bajo `.rs`/`.inc`).
3. Toda prueba unitaria citada existe **literalmente** en `mc-aot/src`.
4. Los dos oráculos existen, están en la suite y cada línea que el contrato dice que observan aparece en el `.java` **y** en su runner `.py`.
5. Cada evidencia citada de `analysis/` existe.
6. Cada responsable citado es una tarea real de `TODO.md`.
7. Este documento y el JSON no divergen: no hay casos sin documentar ni identificadores inventados.

Lo que **no** verifica: la semántica. Eso solo lo demuestran los diferenciales citados, y cada uno tiene su propio log. Un verde del verificador significa «el contrato no miente sobre sus fuentes», no «el adaptador es correcto».

## 3. Oráculos Java que fijan la semántica

| id | Oráculo | Runner | Suite | Rondas | Qué fija |
|---|---|---|---|---|---|
| `cf` | `mc-aot/tests/CompletableFutureOracle.java` | `check-completable-future-oracle.py` | sí | 40 | Identidad/null, `complete` único, fallo (`join` → `CompletionException`, `get` → `ExecutionException` con la **misma** causa), cancelación de pendiente, `allOf`, hilos y executor de callbacks, `TimeoutException`, interrupción de `get` vs `join` |
| `fjp-handler` | `mc-aot/tests/ForkJoinHandlerOracle.java` | `check-forkjoin-handler-oracle.py` | **añadido en este PR, pendiente de C** | 40 | El handler recibe la excepción de `execute` con identidad de `Throwable` y de hilo; `submit`, `submit(Callable)` y `supplyAsync` **no** lo invocan; `submit(Callable)` **envuelve** la causa; `invoke()` relanza la original o su causa; `commonPool()` estable; contadores de workers dentro del paralelismo; `shutdown` + `awaitTermination` + rechazo |

Evidencia de los oráculos: `analysis/completable-future-java25-oracle.log` y `analysis/forkjoin-handler-java25-oracle.log`.

Los oráculos corren 40 rondas porque la semántica de hilos y de handler no es determinista en una sola pasada; se comparan invariantes, no orden de ejecución. Algunas formas concretas varían entre rondas (por ejemplo `invoke()` rellanzando la instancia original o un envoltorio), así que las aserciones exigen solo lo estable.

## 4. Estados del contrato

| Estado | Significado | Qué exige el verificador |
|---|---|---|
| `differential` | Java 25 contra nativo, en un test del repositorio | test existente y **en la suite** |
| `guard` | El nativo rechaza el caso con un mensaje literal | mensaje presente en `mc-aot/src` |
| `unit` | Solo prueba unitaria Rust; sin comparación con Java | nombre de test presente en `mc-aot/src` |
| `java-only` | Semántica fijada por oráculo, sin contraparte nativa | caso ligado a un oráculo declarado |
| `unsupported` | Ni diferencial ni guarda dedicada: rechazo genérico o nada | responsable y explicación de lo que falta |

## 5. Matriz por operación

| Operación | Casos | Diferencial | Guarda | Unitaria | Solo Java | Falta |
|---|---|---|---|---|---|---|
| `execute` | 2 | 1 | 1 | — | — | — |
| `submit` | 3 | 1 | — | — | 1 | 1 |
| `join` | 3 | 2 | 1 | — | — | — |
| `get` | 1 | — | — | — | — | 1 |
| `constructor` | 5 | 2 | 3 | — | — | — |
| `lifecycle` | 14 | 3 | 2 | 7 | 1 | 1 |
| `shutdown` | 2 | 1 | — | 1 | — | — |
| `awaitTermination` | 2 | 1 | 1 | — | — | — |
| `shutdownNow` | 1 | — | 1 | — | — | — |
| `rechazo` | 1 | 1 | — | — | — | — |
| `worker` | 4 | 2 | 2 | — | — | — |
| `completedFuture` | 6 | 5 | 1 | — | — | — |
| `futuro pendiente` | 11 | 4 | 3 | 3 | 1 | — |
| `fallo de futuro` | 1 | — | 1 | — | — | — |
| `perfil` | 4 | — | 4 | — | — | — |
| `composición` | 5 | — | — | — | — | 5 |
| `errores` | 4 | — | — | — | 4 | — |
| `cancelación` | 1 | — | — | — | 1 | — |
| `timeout` | 1 | — | — | — | 1 | — |
| `interrupción` | 2 | — | — | — | 2 | — |
| `estrés` | 4 | — | — | 4 | — | — |
| `frontera A` | 6 | — | — | 6 | — | — |
| `referencias mutables` | 3 | 1 | 1 | 1 | — | — |
| **Total** | **86** | **24** | **21** | **22** | **11** | **8** |

## 6. Detalle de los casos

### 6.1 `execute` y `submit`/`join`

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `exec.runs-runnable` | `execute(Runnable)` despacha a un worker sin esperar; el `Runnable` puede lanzar | diferencial | `check-rayon-java-forkjoin.py`, `check-real-tracing-shutdown.py` | B-02 |
| `exec.throws-runs-handler` | Si el `Runnable` lanza, el pool invoca su handler con el `Throwable` original | guarda: `execute Runnable falló; excepciones Java no soportadas` | oráculo `fjp-handler` | B-06 |
| `submit.join-value` | `submit(Runnable)` devuelve `ForkJoinTask`; `join()` espera | diferencial | `check-rayon-java-forkjoin.py`, `check-rayon-java-worker-lifecycle.py` | B-02 |
| `submit.join-repeat` | `join()` repetido no relanza trabajo; `join` tras `shutdown` sigue válido | diferencial | `check-rayon-java-forkjoin.py` | B-02 |
| `submit.join-nested-same-pool` | Un worker puede enviar y esperar tareas del mismo pool | diferencial | `check-rayon-java-forkjoin.py`, `check-rayon-forkjoin-profile.py` | B-02 |
| `submit.throws-join-diagnostic` | `join()` de una tarea fallida relanza la excepción original sin envolver | guarda: `ejecución concurrent-int` (diagnóstico y exit 2) | `check-rayon-java-forkjoin.py` | B-04 |
| `submit.get-execution` | `ForkJoinTask.get()` envuelve en `ExecutionException`; `get(timeout)` da `TimeoutException` | **falta** | oráculo `fjp-handler` | B-04 |
| `submit.throws-no-handler` | `submit` **no** invoca el handler: el fallo se observa en `join`/`get` | solo-Java | oráculo `fjp-handler` | B-04 |
| `submit.callable-value` | `submit(Callable)` devuelve el valor; con fallo, `get()` lanza `ExecutionException` | **falta** | oráculo `fjp-handler` | B-04 |
| `submit.callable-cause-wrapped` | En `submit(Callable)` la causa **no** conserva identidad: `getCause()` es un envoltorio nuevo, y el handler no se invoca | solo-Java | oráculo `fjp-handler` | B-04 |
| `submit.invoke-rethrows` | `invoke()` relanza la original o una cuyo `cause` es la original; el handler no participa | solo-Java | oráculo `fjp-handler` | B-04 |

Nota de frontera: el nativo solo traduce `submit(Runnable)` y `join()`. `execute` con excepción **termina el proceso** con diagnóstico en vez de llamar a un handler que no existe.

### 6.2 Pool, lifecycle y rechazo

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `pool.ctor-parallelism` | `new ForkJoinPool(int)` fija paralelismo; fuera de rango es error | diferencial + guarda `paralelismo fuera del perfil 1..255` | `check-rayon-java-forkjoin.py` | B-02 |
| `pool.ctor-four-args-null-handler` | Constructor de 4 argumentos con handler `null` y factory por defecto | diferencial | `check-rayon-java-worker-lifecycle.py`, `check-rayon-java-forkjoin.py` | B-02 |
| `pool.ctor-handler-non-null` | El handler recibe la excepción de `execute` en el hilo worker | guarda: `handler personalizado no soportado` | oráculo `fjp-handler` | B-06 |
| `pool.ctor-custom-java-factory` | Una factory Java arbitraria crea workers con su propio estado | guarda: `factory Java no trivial` | `check-rayon-java-forkjoin.py` | B-02 |
| `pool.ctor-custom-factory-profile` | El modo `async` y el número de workers los decide el constructor | guarda: `factory personalizada requiere un worker y async=true` | `check-rayon-java-worker-lifecycle.py` | B-02 |
| `pool.lazy-start` | Java crea workers al construir; aquí se crean al primer envío | unitaria `constructor_and_unused_shutdown_do_not_start_workers` | `mc-aot/src/executor_runtime.rs` | B-02 |
| `pool.shutdown-idempotent` | `shutdown()` es idempotente y no cancela lo ya enviado | diferencial | `check-rayon-java-forkjoin.py` | B-02 |
| `pool.await-termination` | `awaitTermination` devuelve `true`/`false`; siete unidades de `TimeUnit` | diferencial | `check-rayon-java-worker-lifecycle.py`, `check-rayon-forkjoin-profile.py`, `analysis/rayon-await-validation.log` | B-02 |
| `pool.await-self` | Desde un worker del mismo pool Java puede bloquear o vencer | guarda: `awaitTermination desde worker propio no soportado` | `mc-aot/src/executor_runtime.rs` | B-02 |
| `pool.shutdown-now` | `shutdownNow()` cancela, interrumpe y devuelve tareas no iniciadas | guarda: `shutdownNow no soportado` | `check-real-tracing-shutdown.py` | B-02 |
| `pool.reject-after-shutdown` | Tras `shutdown`, `execute`/`submit` lanzan `RejectedExecutionException` | diferencial de la condición + guarda `pool cerrado` | `check-rayon-java-forkjoin.py` | B-02 |
| `pool.close-does-not-keep-alive` | Un futuro completado no mantiene vivo el pool cerrado | unitaria `completed_future_does_not_keep_shutdown_pool_alive` | `mc-aot/src/executor_runtime.rs` | B-02 |
| `pool.no-global-pool-fallback` | Ningún fallo de factory puede degradar al pool común | unitaria `rejected_hooks_never_fall_back_to_default_pool` | `mc-aot/src/executor_runtime.rs` | B-02 |
| `pool.single-pool-per-object` | Un `ForkJoinPool` tiene una sola identidad e inicialización | unitaria `racing_first_use_creates_only_one_pool` | `mc-aot/src/executor_runtime.rs` | B-02 |

`pool.reject-after-shutdown` es el ejemplo canónico de por qué este documento existe: la **condición** coincide con Java, el **mecanismo** no (diagnóstico y salida, no `RejectedExecutionException`). Se declara rechazo observado; no se presenta como equivalencia de excepciones.

### 6.2bis Consultas de lifecycle (B-02)

Seis perfiles de consulta no bloqueantes del `ForkJoinPool` restringido, con diferencial Java 25 nuevo
(`mc-aot/tests/check-rayon-java-pool-queries.py`, 24 resultados) y cuatro pruebas del runtime.

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `pool.query-is-shutdown` | `isShutdown()` false hasta el cierre, true después, también por la interfaz `ExecutorService`; no implica terminación | diferencial | `check-rayon-java-pool-queries.py` | B-02 |
| `pool.query-is-terminated` | `isTerminated()` false con trabajo pendiente o pool abierto; true tras cierre sin tareas y en un pool nunca usado; no espera | diferencial | `check-rayon-java-pool-queries.py`, `rayon_pool_queries.rs` | B-02 |
| `pool.query-parallelism` | `getParallelism()` devuelve el valor configurado y se conserva tras el cierre | diferencial | `check-rayon-java-pool-queries.py` | B-02 |
| `pool.query-termination-requires-rayon` | Java siempre responde; el adaptador no puede sin hilos que observar | guarda: `terminación real requiere Rayon` | `mc-aot/src/executor_runtime.rs` | B-02 |
| `pool.query-unsupported-counts` | `getActiveThreadCount`, `getPoolSize`, `getRunningThreadCount`, `getQueuedSubmissionCount` informan del estado interno | guarda: `clase no encontrada en versiones ni bibliotecas` (sin guarda dedicada) | `check-rayon-java-pool-queries.py` | B-02 |
| `pool.query-unit-crate-path` | Un pool nunca usado queda terminado al cerrarse | unitaria `never_started_pool_is_terminated_after_shutdown` | `mc-aot/src/executor_runtime.rs` | B-02 |
| `pool.query-real-workers` | Las tres consultas siguen el ciclo real de los trabajadores | unitaria `queries_track_real_worker_lifecycle` | `mc-aot/tests/rayon_pool_queries.rs` | B-02 |
| `pool.shutdown-non-blocking` | `shutdown()` **no** espera a las tareas en curso; `isTerminated()` es false mientras corren | unitaria `running_task_keeps_pool_not_terminated` | `mc-aot/tests/rayon_pool_queries.rs` | B-02 |
| `pool.query-foreign-ids` | Una referencia a otro pool no se responde como propia | unitaria `foreign_pool_ids_are_rejected_not_answered` | `mc-aot/tests/rayon_pool_queries.rs` | B-02 |
| `pool.common-pool` | `commonPool()` devuelve siempre la misma instancia con paralelismo ≥ 1 | **falta** (exige pool global; hoy sin guarda) | oráculo `fjp-handler` | B-02 |
| `pool.worker-counters` | Los contadores de workers no exceden el paralelismo y hay al menos uno tras usarlo | solo-Java | oráculo `fjp-handler` | B-02 |

`pool.shutdown-non-blocking` es una comprobación que faltaba y que ahora está cubierta con tarea de 300 ms:
el cierre vuelve en menos de 250 ms y la terminación llega después del `join`. En el crate, en cambio,
`isTerminated()` se rechaza porque el scheduler de reserva no tiene hilos que observar
(`pool.query-termination-requires-rayon`); el perfil real vive en el adaptador Rayon que se embebe en el
programa generado.

### 6.3 Workers

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `worker.onstart-ontermination` | `onStart` una vez al arrancar, `onTermination` al terminar | diferencial | `check-rayon-java-worker-lifecycle.py`, `check-real-util-worker-onstart.py` | B-02 |
| `worker.name` | `setName`/`getName` y nombre de hilo observables | diferencial | `check-rayon-java-worker-lifecycle.py`, `analysis/rayon-worker-name-validation.log` | B-02 |
| `worker.override-run-start` | Un worker puede sobrescribir `run`/`start` | guarda: `worker con override run/start no soportado` | `mc-aot/src/concurrent_compile.rs` | B-02 |
| `worker.util-logger-pending` | `Util.makeExecutor` referencia `Util.LOGGER` y `Util.onThreadException` | guarda: `campo externo no soportado` | `check-real-util-worker-guards.py` | B-06 |

`worker.util-logger-pending` documenta el bloqueo real del arranque: sin `Logger` no hay factory de Minecraft, y `log4rs` sigue aparcado. La guarda evita sustituirlo por un logger ficticio.

### 6.4 Futuros: el perfil `completedFuture` que ya existe

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `future.completed-identity-null` | `completedFuture(v)` ya completado; `null` atraviesa `join`/`get`/`getNow`; instancias distintas | diferencial | `check-rayon-completed-future.py`, `check-numeric-completed-future.py` | B-03 |
| `future.completed-queries` | `isDone`/`isCancelled`/`isCompletedExceptionally`/`getNow` coherentes | diferencial | los anteriores + `check-real-chunk-passthrough-future.py` | B-03 |
| `future.completed-cells` | `complete`/`cancel` sobre completado devuelven `false` y no cambian el valor | diferencial | `check-rayon-completed-future.py`, `check-numeric-completed-future.py` | B-03 |
| `future.completed-shared-workers` | Varios workers leen el mismo futuro completado a la vez que el llamador | diferencial | `check-rayon-shared-completed-future.py` | B-03 |
| `future.completed-real-passthrough` | `ChunkStatusTasks.passThrough` devuelve `completedFuture(chunk)`, admite `null` y conserva identidad | diferencial | `check-real-chunk-passthrough-future.py` (hash de classfile verificado) | B-03 |
| `future.pending-state` | Pendiente: `isDone()==false`, `getNow(x)==x`, completo único | **diferencial** (B-03) | `check-rayon-pending-future.py` | B-03 |
| `future.obtrude` | `obtrudeValue`/`obtrudeException` fuerzan el resultado | guarda: `CompletableFuture: operación no soportada` | `check-numeric-completed-future.py` | B-03 |
| `future.complete-exceptionally` | `completeExceptionally` → `join`/`get` con la misma causa | guarda: `CompletableFuture: operación no soportada` | oráculo `cf` | B-03 |
| `future.optin-rayon` | La semántica de futuro no depende de variables de entorno | guarda: `completedFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1` | `check-rayon-completed-future.py` | B-03 |
| `future.optin-numeric` | Ídem para el backend principal monohilo | guarda: `CompletableFuture: requiere MC_AOT_NUMERIC_COMPLETED_FUTURE=1` | `check-numeric-completed-future.py` | B-03 |
| `future.capture-final` | Java permite capturar referencias mutables | guarda: `captura CompletableFuture debe ser final` | `check-rayon-shared-completed-future.py` | B-03 |
| `future.only-completed-heap` | Un `CompletableFuture` Java puede estar en cualquier estado | guarda: `solo completado normal del perfil` | `check-numeric-completed-future.py` | B-03 |

Aquí se ve la frontera exacta del perfil actual: **futuro ya completado normalmente, sin transiciones, y solo si se activa un opt-in distinto por backend**. Todo lo demás (pendiente, fallo, cancelación) está rechazado hoy.

### 6.4bis Futuro pendiente con completado normal (B-03)

Primer subperfil de futuros pendientes: **estado pendiente → completado normal**, sin estado fallido,
sin cancelación efectiva y sin esperas. Implementado en el backend concurrente; el perfil de
`completedFuture` se conserva tal cual, y el backend numérico sigue rechazando `new` (`new no soportado`).

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `future.pending-state` | Recién creado: pendiente, `isDone()==false`, `getNow(x)==x`, completo único | diferencial | `check-rayon-pending-future.py` | B-03 |
| `future.pending-queries` | `isDone`, `isCancelled`, `isCompletedExceptionally` y `getNow` sin completar | diferencial | `check-rayon-pending-future.py` | B-03 |
| `future.pending-complete-once` | `complete(v)` true y luego false; valor fijado, incluido `null` | diferencial | `check-rayon-pending-future.py` | B-03 |
| `future.pending-publication` | Se publica pendiente en un campo final de otra clase y se completa después | diferencial | `check-rayon-pending-future.py` | B-03 |
| `future.pending-join-blocked` | `join`/`get` de un pendiente esperan en Java | guarda de ejecución: `join de futuro pendiente no soportado` | `check-rayon-pending-future.py` | B-03 |
| `future.pending-cancel` | `cancel(false)`/`cancel(true)` de un pendiente son efectivos; `get`/`join` lanzan `CancellationException` | guarda de ejecución con ambas banderas: `cancel de futuro pendiente no soportado` | `check-rayon-pending-future.py` | B-03 |
| `future.cancel-pending` | `cancel(true)` y `cancel(false)` son indistinguibles: `true`, `isCancelled`, `get`/`join`/`getNow` con `CancellationException`, `complete` posterior `false`; sobre completado, `false` | solo-Java medido (oráculo `cancel-pending`, 40 rondas por bandera) | `CompletableFutureCancelOracle.java` | B-03 |
| `future.pending-unit-heap` | Estado pendiente, finalización única y consultas coherentes en el heap | unitaria `pending_future_completes_once_and_reports_state` | `mc-aot/src/concurrent_heap.rs` | B-03 |
| `future.pending-unit-foreign` | Un objeto que no es futuro o un valor de otro heap no puede completarlo | unitaria `pending_future_rejects_foreign_objects_and_values` | `mc-aot/src/concurrent_heap.rs` | B-03 |
| `future.pending-completion-race` | Varios `complete` concurrentes: exactamente uno gana | unitaria `pending_future_completion_race_has_single_winner` | `mc-aot/tests/rayon_stress.rs` | B-08 |

Diferencia declarada: publicar un futuro **pendiente** en un campo final es nuevo; antes solo se admitía
completado. Es lo que hace el código real de Minecraft, pero el campo sigue teniendo que ser `final`
(guarda `captura CompletableFuture debe ser final`).

### 6.7 Estrés e invariantes (B-08)

Se comparan invariantes, nunca órdenes que Java no garantiza. Cada prueba corre bajo un perro guardián:
si el cuerpo no termina en el plazo, el fallo es «posible bloqueo» y no un test colgado.

| id | Invariante | Repeticiones | Evidencia | Tarea |
|---|---|---|---|---|
| `stress.monitor-alias-rmw` | Monitor reentrante, alias y RMW atómico dan el total exacto | 20 rondas × 4 trabajadores × 500 incrementos | `monitor_alias_and_rmw_repeat` | B-08 |
| `stress.publication-reads` | Lo publicado antes de liberar a los trabajadores es visible y no se altera | 20 × 4 × 250 lecturas | `publication_then_concurrent_reads_repeat` | B-08 |
| `stress.completion-races` | `join` concurrente y repetido: todos terminan y el trabajo se hace una vez | 20 rondas × 8 tareas × 3 hilos | `completion_races_repeat` | B-08 |
| `stress.close-race` | Cada envío se acepta (y termina) o se rechaza; no se pierde ninguna tarea aceptada | 30 rondas con cierre concurrente | `close_race_keeps_every_task_or_rejects_it` | B-08 |
| `future.pending-completion-race` | Un solo `complete` gana la carrera | 20 × 4 × 50 intentos | `pending_future_completion_race_has_single_winner` | B-08 |

| `gap.two-optins` | **Cerrado** en Q-AB-2: nombre canónico `MC_AOT_FUTURES=restricted` con el alias histórico una versión, `off` lo apaga y un valor ajeno se rechaza | B lo implementó en su rama y A en `numeric.rs`; ver `analysis/discussion/threads/a-b.md` | `B-07` |

El hueco `gap.two-optins` quedó **cerrado** en Q-AB-2: el backend concurrente acepta el nombre canónico
`MC_AOT_FUTURES=restricted` y el alias histórico durante una versión, y rechaza valores ajenos
(caso `futures.optin-canonical`).

### 6.8 Frontera para el frente A (B-07)

Interfaz documentada en [`b-api-for-a.md`](b-api-for-a.md) y verificada por pruebas de frontera.
No amplía el perfil: fija cómo A debe usarlo.

| id | Qué fija | Evidencia |
|---|---|---|
| `api.create-bounds` | Paralelismo 1..=255; sin doble registro | `create_accepts_only_the_declared_parallelism` |
| `api.submit-join-scoped` | Identidad por tarea, `join` idempotente, ids ajenos rechazados | `submit_and_join_are_idempotent_and_scoped` |
| `api.await-callers-only` | Solo el llamador espera el cierre | `await_termination_is_callers_only` |
| `api.close-final` | Cierre idempotente y definitivo; paralelismo conservado | `close_is_idempotent_and_final` |
| `api.publication-to-worker` | Objeto publicado visible y con identidad en la tarea | `pending_future_published_to_a_worker_is_visible` |
| `api.foreign-heap-ids` | Referencias de otro heap rechazadas | `foreign_heap_references_are_rejected` |

### 6.9 Referencias mutables en el backend concurrente (B-09)

Acordado con A en `Q-AB-1`. El opt-in es `MC_AOT_RAYON_MUTABLE_REFS=1`; sin él la traducción se rechaza, y un
campo `final` sigue sin admitir escrituras fuera del constructor. La escritura pasa por el mutex del heap y el
destino debe estar publicado y ser de la clase esperada.

| id | Semántica Java | Estado | Evidencia | Tarea |
|---|---|---|---|---|
| `mutable.ref-nonfinal` | Campo de referencia no `final` escrito fuera del constructor y leído después | diferencial | `check-rayon-mutable-refs.py` (28 valores por fixture) | B-09 |
| `mutable.ref-requires-optin` | Sin declaración explícita no hay referencias compartidas escribibles | guarda: `concurrent-int: captura de referencia debe ser final` | `check-rayon-mutable-refs.py` | B-09 |
| `mutable.ref-relink-stress` | Reenlazar bajo monitor no pierde nodos ni crea ciclos | unitaria `relink_under_monitor_keeps_the_chain_whole` | `mc-aot/tests/rayon_stress.rs` | B-09 |

**Diferencia declarada:** lo que se garantiza es que la escritura es atómica bajo el mutex del heap y que los
invariantes probados se cumplen; **no** que se reproduzca el *happens-before* del modelo de memoria de Java.

### 6.5 Composición (lo que pide Minecraft y aún no existe)

| id | Semántica Java | Estado | Tarea |
|---|---|---|---|
| `comp.supply-async` | `supplyAsync(supplier, pool)`: ejecuta en el pool; el fallo llega como `CompletionException` con causa idéntica y no toca el handler | falta (oráculo `fjp-handler`) | B-05 |
| `comp.then-apply` | `thenApply` sin executor corre en el hilo que completa | falta (oráculo `cf`) | B-05 |
| `comp.then-apply-async-executor` | `thenApplyAsync(fn, executor)` usa el executor una vez; rechazo ⇒ `RejectedExecutionException` | falta (oráculo `cf`) | B-05 |
| `comp.allof` | `allOf` espera a todos, propaga la misma causa; `allOf()` vacío da `null` | falta (oráculo `cf`) | B-05 |
| `comp.then-compose` | `thenCompose` aplana futuros anidados y propaga fallos | falta (**sin oráculo**) | B-05 |

`comp.then-compose` está a propósito sin oráculo: el contrato no puede fijar semántica que nadie ha medido. Primer paso de B-05 es ampliar el oráculo, no implementar.

### 6.6 Errores, cancelación, timeout e interrupción

| id | Semántica Java | Estado | Tarea |
|---|---|---|---|
| `err.handler-identity` | El handler recibe el `Throwable` original y el hilo worker | solo-Java (oráculo `fjp-handler`) | B-04 |
| `err.join-vs-get-types` | Futuro fallido: `join` → `CompletionException`, `get` → `ExecutionException`; `ForkJoinTask.join` relanza sin envolver | solo-Java (oráculos `cf`, `fjp-handler`) | B-04 |
| `err.cancel-pending` | `cancel(false)` de un pendiente ⇒ `isCancelled()` y `CancellationException` directa | solo-Java (oráculo `cf`) | B-03 |
| `err.timeout-get` | `get(timeout, unit)` → `TimeoutException` sin completar el futuro | solo-Java (oráculo `cf`) | B-04 |
| `err.interrupt-get` | Interrumpir un `get` bloqueado lanza `InterruptedException` y limpia el flag | solo-Java (oráculo `cf`) + opt-in `MC_AOT_RAYON_ASSUME_NO_INTERRUPT=1` | B-04 |
| `err.join-interrupt` | `join()` **no** lanza `InterruptedException`: conserva el valor y el flag | solo-Java (oráculo `cf`) | B-04 |

## 7. Lo que hoy se rechaza (mensajes literales)

Estos mensajes existen en `mc-aot/src` y el verificador lo comprueba; cualquiera de ellos es un rechazo declarado, **no** una equivalencia:

```text
execute Runnable falló; excepciones Java no soportadas      (execute que lanza)
ejecución concurrent-int                                    (fallo de tarea / limpieza)
handler personalizado no soportado                          (constructor de 4 args con handler)
factory Java no trivial                                     (factory arbitraria)
factory personalizada requiere un worker y async=true       (subperfil de factory)
paralelismo fuera del perfil 1..255                         (constructor)
pool cerrado                                                (envío tras shutdown)
awaitTermination desde worker propio no soportado           (autobloqueo)
shutdownNow no soportado                                    (cancelación/interrupción)
worker con override run/start no soportado                  (worker)
campo externo no soportado                                  (Util.LOGGER y compañía)
CompletableFuture: operación no soportada                   (obtrudeValue, completeExceptionally…)
solo completado normal del perfil                           (heap numérico)
captura CompletableFuture debe ser final                    (publicación)
*MC_AOT_RAYON_COMPLETED_FUTURE=1 / *MC_AOT_NUMERIC_COMPLETED_FUTURE=1   (opt-in)
MC_AOT_RAYON_ASSUME_NO_INTERRUPT=1                          (interrupción no modelada)
```

## 8. Huecos detectados al hacer este contrato

| id | Hallazgo | Qué lo cierra |
|---|---|---|
| `gap.handler-oracle-not-in-suite` | `check-forkjoin-handler-oracle` existía pero **no** estaba en `run-regressions.sh`: la prueba de handler no corría en la integral | añadida aquí la entrada (y la del verificador); **C debe confirmarla** |
| `gap.no-explicit-guard-for-task-get` | `ForkJoinTask.get()`/`invoke()` no tienen guarda propia: caen en el rechazo genérico de llamada externa, indistinguible de un error de traducción | B-04: guarda explícita + caso en el oráculo antes de modelar |
| `gap.oracle-missing-cases` | Los oráculos no cubren `submit(Callable)`, `execute(ForkJoinTask)`, `invoke()`, `commonPool()`, `ManagedBlocker`, interrupción de workers, `toString` del pool, `thenCompose`, `thenAccept`, `handle`, `exceptionally`, `anyOf`, `orTimeout`, `completeAsync`, `cancel(true)` | B-02/B-04/B-05 amplían por subperfil **antes** de implementar |
| `gap.pending-future-waits` | No hay espera sobre un futuro pendiente (`join`/`get`) ni cancelación: reciben guarda de ejecución. Tampoco hay callbacks ni composición | B-03/B-04 necesitan el modelo de excepciones y una espera entre frames acordada con A |
| `gap.no-guard-for-lifecycle-queries` | `getActiveThreadCount`, `getPoolSize`, `getRunningThreadCount` y `getQueuedSubmissionCount` no tienen guarda ni mensaje propio: caen en el rechazo de carga de clase JDK | B-02 decide si se modelan o se rechazan con mensaje explícito |
| `gap.no-java-differential-for-unit-cases` | Cuatro propiedades del lifecycle solo tienen prueba unitaria Rust | B-02/B-08: diferencial Java observable o declararlas propiedad del adaptador |

## 9. Entradas para el resto del frente B

Estas son las consecuencias operativas del contrato; no sustituyen los criterios de `TODO.md`.

- **B-02 · Lifecycle.** El perfil ya cubierto es: constructor `(I)` y `(I, factory, null, boolean)` restringido, `execute`/`execute` por interfaz, `submit(Runnable)`, `join`, `shutdown` idempotente, `awaitTermination`, rechazo tras cierre. Falta: factory y handler reales, creación gradual de workers, `shutdownNow`, interrupción, `execute(ForkJoinTask)`, `submit(Callable)`. Cada uno entra como subperfil con guarda hasta que tenga diferencial.
- **B-03 · Futuros pendientes.** **Primer subperfil hecho:** pendiente + completado normal, con publicación en campo final y finalización única (48 resultados contra Java 25). Falta: fallo, cancelación efectiva y espera. No hace falta rediseñar el perfil completado: cinco de los casos `future.completed-identity-null`, `future.completed-queries`, `future.completed-cells`, `future.completed-shared-workers` y `future.completed-real-passthrough` ya son diferenciales.
- **B-04 · `get`/`join` y fallos.** **Bloqueada por decisión, no por código:** el oráculo `fjp-handler` y `err.*` fijan tres mecanismos distintos (`CompletionException`, `ExecutionException`, relanzado directo). Antes de implementar, hay que decidir con A cómo se representa un `Throwable`; hoy un fallo termina el proceso y eso debe seguir siendo explícito, no convertirse en excepción inventada.
- **B-05 · Composición.** Orden de prioridad según rutas comprobadas: `supplyAsync` → `thenApply` → `allOf` → `thenApplyAsync` con executor → `thenCompose`. El primero exige el handler/executor de B-06; el último exige ampliar el oráculo.
- **B-06 · Factory y handler de `Util`.** **Bloqueo caracterizado a nivel de bytecode** en [`b06-util-factory-blockers.md`](b06-util-factory-blockers.md): la factory crea una subclase de `ForkJoinWorkerThread` con `onStart`/`onTermination`, `onStart` llama a Tracy y `onTermination` registra por slf4j (el logging está aparcado). Hallazgo: el `clamp(…, 1, …)` de Minecraft justifica el perfil 1..255 y la rama Guava es inalcanzable. Propuesta en dos pasos (nombrado only; logging después), subordinada a B-04.
- **B-07 · Interfaz para A.** **Entregada y verificada** en [`b-api-for-a.md`](b-api-for-a.md) con seis pruebas de frontera; queda abierta la unificación del opt-in (`gap.two-optins`) y las tres decisiones de §6 de ese documento.
- **B-08 · Estrés.** Los invariantes a repetir ya están aislados: `join` repetido, `join` anidado en el mismo pool, finalización única, rechazo tras cierre, cierre que no espera a futuros completados.

## 10. Criterios de cierre de B-01

- [x] Los dos oráculos convertidos en matriz de casos con estado y evidencia.
- [x] Cada afirmación del contrato verificable por máquina (`check-futures-contract.py`, exit 0).
- [x] Guardas citadas literalmente desde `mc-aot/src`.
- [x] Huecos declarados, con tarea responsable y acción.
- [x] **B-09 entregada:** referencias mutables con opt-in, 84 resultados contra Java 25, guarda sin opt-in y estrés de reenlazado.
- [x] **Caso de cancelación colapsado (Q-BC-8):** un solo `future.cancel-pending` con la medición de las dos banderas.
- [x] **83 casos con tercer oráculo:** cancelación de pendiente medida en `CompletableFutureCancelOracle.java` (40 rondas por bandera).
- [x] **B-07 entregada:** interfaz para A en `analysis/b-api-for-a.md` con seis pruebas de frontera.
- [x] **Subperfiles B-03 y B-08 verificados:** futuro pendiente con completado normal (48 resultados Java 25) y cinco pruebas de estrés con invariantes y perro guardián.
- [x] **Quince pruebas focalizadas ejecutadas** con JDK 25.0.5 y el bundle oficial verificado; log único `analysis/b02-futures-suite-jdk25.log` (14/14 OK) y `cargo test` 64+30+30.
- [ ] **C integra** `check-forkjoin-handler-oracle`, `check-futures-contract` y `check-rayon-java-pool-queries` en `run-regressions.sh` (líneas preparadas en este PR, sin ejecutar la integral aquí).
- [ ] Integral completa (`run-regressions.sh`, ~306 etapas) verde, con su log archivado. Aquí solo corrió el subconjunto del frente B.
- [ ] Revisión cruzada de A (frontera de excepciones y ownership) y de B-02/B-04 (exactitud del perfil).

Mientras falten las tres últimas casillas, B-01 está **en revisión**, no terminada.

## 11. Reproducción y limitación de esta sesión

Comandos exactos de las pruebas que el contrato cita (requieren `JAVA_HOME` = JDK 25, el bundle del `README.md` y Rust):

```sh
python3 mc-aot/tests/check-completable-future-oracle.py
python3 mc-aot/tests/check-forkjoin-handler-oracle.py
python3 mc-aot/tests/check-rayon-java-forkjoin.py
python3 mc-aot/tests/check-rayon-java-worker-lifecycle.py
python3 mc-aot/tests/check-rayon-forkjoin-profile.py
python3 mc-aot/tests/check-rayon-completed-future.py
python3 mc-aot/tests/check-rayon-shared-completed-future.py
python3 mc-aot/tests/check-numeric-completed-future.py
python3 mc-aot/tests/check-real-chunk-passthrough-future.py
python3 mc-aot/tests/check-real-tracing-shutdown.py
python3 mc-aot/tests/check-real-util-worker-guards.py
python3 mc-aot/tests/check-real-util-worker-onstart.py
python3 mc-aot/tests/check-futures-contract.py            # solo Python, sin Java ni cargo
```

**Entorno de ejecución de este trabajo:** se provisionó dentro del sandbox Temurin **25.0.5** y el bundle
oficial del `README.md`, con los dos hashes verificados (`server-26.3.jar` sha1 `33680f5f…`, interno
sha256 `a362163e…`), además de Rust 1.99.1. Resultado de la última pasada:

| Comprobación | Resultado |
|---|---|
| Integral completa (`bash mc-aot/run-regressions.sh`) | **exit 0, 310 etapas** — `analysis/full-regressions-b-frente-contrato-futures-retry3.log` |
| `cargo test` | 66 del binario + 32 `rayon_await` + 32 `rayon_pool_queries` + 33 `rayon_stress` + 34 `rayon_b_api`, 0 fallos |
| 15 pruebas focalizadas del frente B | 15 OK; log `analysis/b03-b08-futures-suite-jdk25.log` |
| `check-rayon-java-pool-queries.py` | 24 resultados Java 25/Rayon + guarda de traducción |
| `check-rayon-pending-future.py` (nuevo) | 48 resultados Java 25/Rayon + 3 líneas del oráculo de cancelación + 2 guardas de traducción + 3 de ejecución |
| `CompletableFutureCancelOracle.java` (nuevo) | 40 rondas por bandera: `cancel(true)` y `cancel(false)` son indistinguibles |
| Integral completa (`run-regressions.sh`) | **no ejecutada aquí**: responsabilidad de C |

Los JAR y el JDK se guardaron fuera del árbol versionado (`/downloads` está en `.gitignore` y en
`.git/info/exclude`; el JDK vive en la caché del entorno), así que no se sube ningún binario ajeno.

## 12. Lista de PR para este cambio

- [x] ID/título (B-01), alcance, archivos: `analysis/futures-contract-b01.{md,json}`, `mc-aot/tests/check-futures-contract.py`, dos líneas en `mc-aot/run-regressions.sh`.
- [x] Comportamiento implementado (B-02): tres consultas de lifecycle del `ForkJoinPool` restringido (`isShutdown`, `isTerminated`, `getParallelism`) sobre `pools`/`LazyPool`, sin excepciones Java ni esperas bloqueantes; `shutdown()` sigue sin esperar tareas.
- [x] Lo que se sigue rechazando: la lista completa de §7, sin cambios.
- [x] Pruebas: `check-futures-contract.py`, `check-rayon-java-pool-queries.py` y las 12 restantes del frente B, ejecutadas aquí con JDK 25.0.5 y Rust 1.99.1; `cargo test` completo en verde. Log archivado: `analysis/b02-futures-suite-jdk25.log`.
- [x] Casos normales, límites, null/alias y carreras: mapeados en la matriz; los que no los tienen quedan en `gap.*`.
- [x] Cambios de contrato con otros frentes: `gap.two-optins` y `gap.no-explicit-guard-for-task-get` son decisiones que necesitan a A/B-04; el handler del oráculo necesita a C.
- [x] Sin JARs, binarios, credenciales ni datos personales en el commit.
- [ ] Integral: **pendiente**, no ejecutada aquí (solo el subconjunto del frente B). No se declara aprobada.
