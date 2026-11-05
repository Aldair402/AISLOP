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
| `cf` | `mc-aot/tests/CompletableFutureOracle.java` | `check-completable-future-oracle.py` | sí | 20 | Identidad/null, `complete` único, fallo (`join` → `CompletionException`, `get` → `ExecutionException` con la **misma** causa), cancelación de pendiente, `allOf`, hilos y executor de callbacks, `TimeoutException`, interrupción de `get` vs `join` |
| `fjp-handler` | `mc-aot/tests/ForkJoinHandlerOracle.java` | `check-forkjoin-handler-oracle.py` | **añadido en este PR, pendiente de C** | 20 | El handler recibe la excepción de `execute` con identidad de `Throwable` y de hilo; `submit` y `supplyAsync` **no** lo invocan; `shutdown` + `awaitTermination` + rechazo |

Evidencia de los oráculos: `analysis/completable-future-java25-oracle.log` y `analysis/forkjoin-handler-java25-oracle.log`.

Los oráculos corren 20 rondas porque la semántica de hilos y de handler no es determinista en una sola pasada; se comparan invariantes, no orden de ejecución.

## 4. Estados del contrato

| Estado | Significado | Qué exige el verificador |
|---|---|---|
| `differential` | Java 25 contra nativo, en un test del repositorio | test existente y **en la suite** |
| `guard` | El nativo rechaza el caso con un mensaje literal | mensaje presente en `mc-aot/src` |
| `unit` | Solo prueba unitaria Rust; sin comparación con Java | nombre de test presente en `mc-aot/src` |
| `java-only` | Semántica fijada por oráculo, sin contraparte nativa | caso ligado a un oráculo declarado |
| `unsupported` | Ni diferencial ni guarda dedicada: rechazo genérico o nada | responsable y explicación de lo que falta |

## 5. Matriz por operación

| Grupo | Casos | Diferencial | Guarda | Unitaria | Solo Java | Falta |
|---|---|---|---|---|---|---|
| `execute` | 2 | 1 | 1 | — | — | — |
| `submit` / `join` | 5 | 3 | 1 | — | 1 | 1 |
| `get` | 1 | — | — | — | — | 1 |
| constructor de pool | 5 | 2 | 3 | — | — | — |
| `shutdown` / `awaitTermination` / `shutdownNow` / rechazo | 5 | 3 | 2 | — | — | — |
| lifecycle solo unitario | 4 | — | — | 4 | — | — |
| workers | 4 | 2 | 2 | — | — | — |
| futuros: `completedFuture`, pendiente, fallo y perfil | 12 | 5 | 7 | — | — | — |
| composición (`supplyAsync`, callbacks, `allOf`) | 5 | — | — | — | — | 5 |
| errores, cancelación, timeout, interrupción | 6 | — | — | — | 6 | — |
| **Total** | **49** | **16** | **16** | **4** | **7** | **6** |

Resumen exacto (lo imprime `check-futures-contract.py --summary`): **49 casos** — diferencial 16, guarda 16, unitaria 4, solo-Java 7, falta 6. Si cambian, cambia el JSON y esta tabla a la vez: el verificador no compara cifras, pero el `.md` y el `.json` deben citarse con los mismos identificadores.

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
| `future.pending-state` | Pendiente: `isDone()==false`, `getNow(x)==x`, completo único | guarda: `CompletableFuture incompleto no soportado` | oráculo `cf` | B-03 |
| `future.obtrude` | `obtrudeValue`/`obtrudeException` fuerzan el resultado | guarda: `CompletableFuture: operación no soportada` | `check-numeric-completed-future.py` | B-03 |
| `future.complete-exceptionally` | `completeExceptionally` → `join`/`get` con la misma causa | guarda: `CompletableFuture: operación no soportada` | oráculo `cf` | B-03 |
| `future.optin-rayon` | La semántica de futuro no depende de variables de entorno | guarda: `completedFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1` | `check-rayon-completed-future.py` | B-03 |
| `future.optin-numeric` | Ídem para el backend principal monohilo | guarda: `CompletableFuture: requiere MC_AOT_NUMERIC_COMPLETED_FUTURE=1` | `check-numeric-completed-future.py` | B-03 |
| `future.capture-final` | Java permite capturar referencias mutables | guarda: `captura CompletableFuture debe ser final` | `check-rayon-shared-completed-future.py` | B-03 |
| `future.only-completed-heap` | Un `CompletableFuture` Java puede estar en cualquier estado | guarda: `solo completado normal del perfil` | `check-numeric-completed-future.py` | B-03 |

Aquí se ve la frontera exacta del perfil actual: **futuro ya completado normalmente, sin transiciones, y solo si se activa un opt-in distinto por backend**. Todo lo demás (pendiente, fallo, cancelación) está rechazado hoy.

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
CompletableFuture incompleto no soportado                   (futuro pendiente)
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
| `gap.two-optins` | Dos variables distintas (`MC_AOT_RAYON_COMPLETED_FUTURE`, `MC_AOT_NUMERIC_COMPLETED_FUTURE`) para el mismo concepto, con mensajes distintos | B-07: una sola interfaz para A |
| `gap.no-java-differential-for-unit-cases` | Cuatro propiedades del lifecycle solo tienen prueba unitaria Rust | B-02/B-08: diferencial Java observable o declararlas propiedad del adaptador |

## 9. Entradas para el resto del frente B

Estas son las consecuencias operativas del contrato; no sustituyen los criterios de `TODO.md`.

- **B-02 · Lifecycle.** El perfil ya cubierto es: constructor `(I)` y `(I, factory, null, boolean)` restringido, `execute`/`execute` por interfaz, `submit(Runnable)`, `join`, `shutdown` idempotente, `awaitTermination`, rechazo tras cierre. Falta: factory y handler reales, creación gradual de workers, `shutdownNow`, interrupción, `execute(ForkJoinTask)`, `submit(Callable)`. Cada uno entra como subperfil con guarda hasta que tenga diferencial.
- **B-03 · Futuros pendientes.** Punto de partida exacto: estado pendiente y transiciones únicas, con `future.pending-state` como caso hoy rechazado. No hace falta rediseñar el perfil completado: cinco de los casos `future.completed-identity-null`, `future.completed-queries`, `future.completed-cells`, `future.completed-shared-workers` y `future.completed-real-passthrough` ya son diferenciales.
- **B-04 · `get`/`join` y fallos.** El oráculo `fjp-handler` y `err.*` fijan tres mecanismos distintos (`CompletionException`, `ExecutionException`, relanzado directo). Antes de implementar, hay que decidir con A cómo se representa un `Throwable`; hoy un fallo termina el proceso y eso debe seguir siendo explícito, no convertirse en excepción inventada.
- **B-05 · Composición.** Orden de prioridad según rutas comprobadas: `supplyAsync` → `thenApply` → `allOf` → `thenApplyAsync` con executor → `thenCompose`. El primero exige el handler/executor de B-06; el último exige ampliar el oráculo.
- **B-06 · Factory y handler de `Util`.** El bloqueo está caracterizado: `handler personalizado no soportado` y `campo externo no soportado` (`Util.LOGGER`). El contrato de handler (`err.handler-identity`) ya está fijado en Java; lo que falta es logger y `CrashReport`, no semántica.
- **B-07 · Interfaz para A.** Debe entregar: crear/enviar/esperar/cerrar, transporte de referencias, y **una** bandera de opt-in, hoy duplicada (`gap.two-optins`).
- **B-08 · Estrés.** Los invariantes a repetir ya están aislados: `join` repetido, `join` anidado en el mismo pool, finalización única, rechazo tras cierre, cierre que no espera a futuros completados.

## 10. Criterios de cierre de B-01

- [x] Los dos oráculos convertidos en matriz de casos con estado y evidencia.
- [x] Cada afirmación del contrato verificable por máquina (`check-futures-contract.py`, exit 0).
- [x] Guardas citadas literalmente desde `mc-aot/src`.
- [x] Huecos declarados, con tarea responsable y acción.
- [ ] **C integra** `check-forkjoin-handler-oracle` y `check-futures-contract` en `run-regressions.sh` (líneas preparadas en este PR, sin ejecutar la integral aquí).
- [ ] Integral verde en una máquina con JDK 25 + Rust, con el log archivado en `analysis/`.
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

**Limitación declarada:** el contrato y el verificador se escribieron en un entorno con **JDK 11, sin Rust y sin los JAR de Mojang**. Allí se ejecutó `check-futures-contract.py` (solo Python) con exit 0; **ningún diferencial Java/nativo de los citados se ejecutó en ese entorno**. Las cifras de resultados (78 decisiones, 312 resultados, 48 casos, 20 rondas…) provienen de los logs de `analysis/` y de los mensajes de cada test, no de una ejecución nueva. Correr la integral es responsabilidad de C.

## 12. Lista de PR para este cambio

- [x] ID/título (B-01), alcance, archivos: `analysis/futures-contract-b01.{md,json}`, `mc-aot/tests/check-futures-contract.py`, dos líneas en `mc-aot/run-regressions.sh`.
- [x] Comportamiento implementado: **ninguno** en el runtime. No hay cambios en `mc-aot/src`: este PR no habilita nada ni cambia perfiles.
- [x] Lo que se sigue rechazando: la lista completa de §7, sin cambios.
- [x] Pruebas: `python3 mc-aot/tests/check-futures-contract.py` (exit 0 en el entorno del autor). Diferenciales citados: **no ejecutados aquí** (JDK 11, sin Rust); sus logs previos son la evidencia.
- [x] Casos normales, límites, null/alias y carreras: mapeados en la matriz; los que no los tienen quedan en `gap.*`.
- [x] Cambios de contrato con otros frentes: `gap.two-optins` y `gap.no-explicit-guard-for-task-get` son decisiones que necesitan a A/B-04; el handler del oráculo necesita a C.
- [x] Sin JARs, binarios, credenciales ni datos personales en el commit.
- [ ] Integral: **pendiente**, no ejecutada aquí. No se declara aprobada.
