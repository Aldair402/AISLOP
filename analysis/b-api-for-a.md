# B-07 — Interfaz de la concurrencia para el frente A

**Tarea:** B-07 de [`TODO.md`](../TODO.md) · **Base:** rama `trabajo/b-01-contrato-futures` · **Fecha:** 2026-11-05
**Consume:** frente A (`A-03`, `A-06`, `A-07`) · **Dueño de la implementación:** frente B
**Estado:** superficie estable documentada y verificada por pruebas de frontera. **No** es un `ForkJoinPool` completo ni un modelo JVM de memoria.

---

## 1. Qué se entrega y qué no

Se entrega una **API de uso** del adaptador concurrente con reglas explícitas de identidad, propiedad,
locks, fallos y clases admitidas, más pruebas de frontera en `mc-aot/tests/rayon_b_api.rs`.
No se entrega:

- equivalencia general con `java.util.concurrent.ForkJoinPool`;
- excepciones Java (ni `RejectedExecutionException`, ni `ExecutionException`, ni `CancellationException`);
- `wait`/`notify`, GC, ni un modelo completo de memoria;
- ejecución de lambdas arbitrarias de `CompletableFuture` (composición sigue en B-05).

Todo lo que no está en §3 se **rechaza** con un mensaje literal; ninguna ruta se completa con un valor inventado.

## 2. Superficie de uso

### 2.1 Pool

| Operación | Semántica | Rechazos |
|---|---|---|
| `Executors::create(id, count)` | Registra el pool; **no** arranca trabajadores | `paralelismo fuera del perfil 1..255`, `pool ya inicializado` |
| `create_with_hooks(id, count, hooks)` | Igual, con factory/onStart/onExit Rust | los mismos, más los de la factory |
| `submit(heap, id, job)` | Encola `job` y devuelve el `ObjectId` de la tarea; arranca el pool en el primer envío | `pool cerrado`, `pool no inicializado`, `submit rechazado` |
| `execute(id, job)` | Igual sin identidad de tarea; si el job falla, el proceso termina con diagnóstico | los mismos |
| `join(task)` | Espera y devuelve el resultado; **idempotente** | `tarea inexistente`, `Runnable devolvió valor`, `falló tarea nativa` |
| `await_termination(id, timeout)` | Espera acotada; `true` si terminó, `false` si venció | `pool no inicializado`, `awaitTermination desde worker propio no soportado` |
| `shutdown(id)` | Cierra el pool; **idempotente**; no cancela lo ya enviado | — |
| `is_shutdown(id)` / `is_terminated(id)` / `parallelism(id)` | Consultas no bloqueantes | `pool no inicializado`, `terminación real requiere Rayon` |

**Contrato de espera (importante para A):** `shutdown()` **no** espera a las tareas en curso; `isTerminated()`
es `false` mientras corren; `awaitTermination` solo se permite desde el llamador, nunca desde un worker del
mismo pool. Está verificado en `running_task_keeps_pool_not_terminated` y `await_termination_is_callers_only`.

### 2.2 Heap y referencias

| Operación | Semántica |
|---|---|
| `allocate(fields)` / `allocate_typed(class, fields)` | Objeto con identidad estable en este heap |
| `read(id, field)` / `write(id, field, value)` | Tipado comprobado; un valor de otro heap se rechaza |
| `enter(id)` | Monitor **reentrante** por objeto; se libera con el guard |
| `get_and_add_int(id, field, delta)` / `compare_exchange(...)` | RMW atómico bajo el lock del heap |
| `mark_pending_future(id)` | Marca el objeto como `CompletableFuture` pendiente (una sola vez) |
| `future_complete(id, value)` | `true` la primera vez, `false` después; atómico entre workers |
| `future_is_done(id)` / `future_get_now(id, default)` | Consultas sin bloquear |
| `completed_future(value)` | Perfil antiguo: futuro ya completado |

Reglas que A debe respetar:

1. **Identidad por heap.** Un `ObjectId` solo es válido en su heap. Se rechaza en otro heap; no hay traducción
   de identificadores entre backends.
2. **Sin copias implícitas.** Publicar un objeto en una tarea es pasar el `ObjectId`; el objecto no se duplica.
3. **Locks.** Un worker puede entrar al monitor de cualquier objeto del heap, de forma reentrante. No hay lock
   global retenido mientras corre una tarea. Si un callback Java se invoca desde dentro de un monitor, ese hecho
   debe declararse en el PR de A: el adaptador no lo detecta.
4. **Ciclos y alias** se admiten tal cual (son los mismos `ObjectId`), pero no hay GC: la vida de los objetos
   es el heap.
5. **Publicación antes de completar**: un futuro pendiente puede publicarse en un campo final y completarse
   después (`pending_future_published_to_a_worker_is_visible`). Es el caso que A-06 necesita.

### 2.3 Referencias mutables (B-09, acordado en Q-AB-1)

A partir de B-09 el backend concurrente admite **campos de referencia no `final`** cuando se declara
`MC_AOT_RAYON_MUTABLE_REFS=1`. Reglas, que son el contrato con A:

1. **Escritura por el mutex del heap.** `heap.write` es la única vía; nunca una escritura directa desde un worker ni
   con el monitor retenido alrededor de la publicación.
2. **Orden de adquisición:** monitor del objeto primero, operación del heap después (su mutex es hoja). El inverso no
   existe en el código generado y no debe introducirse.
3. **Destino comprobado:** el objeto destino debe estar publicado y ser de la clase declarada por el campo; `null` se
   admite como en Java. Un destino de otra clase aborta con diagnóstico en vez de escribirse.
4. **`final` sigue siendo `final`:** un campo de referencia `final` no admite escrituras fuera del constructor, con o
   sin opt-in.
5. **Sin opt-in no hay perfil:** la traducción se rechaza con
   `concurrent-int: captura de referencia debe ser final`, para que una referencia compartida escribible nunca aparezca
   por accidente.

**Diferencia declarada, no equivalencia:** se garantiza que la escritura es atómica bajo el mutex y que los
invariantes probados se cumplen (20 rondas × 4 workers × 100 reenlaces sobre 64 nodos, sin nodos perdidos ni ciclos).
No se garantiza el *happens-before* del modelo de memoria de Java.

### 2.4 Referencias del proyecto como valor de retorno (B-10)

Bajo el mismo `MC_AOT_RAYON_PROJECT_REFERENCES=1` que ya materializaba objetos del proyecto, el backend
concurrente admite métodos del proyecto que devuelven una referencia (`Node step(){return next;}`) y constructores
de firma mixta (`(ILnet/minecraft/...;)V`). Reglas:

1. **Tipo declarado exacto:** el `areturn` comprueba la clase del valor devuelto; `null` se admite como en Java,
   otra clase no. Sin despacho de subclases.
2. **Sin opt-in no hay traducción:** los dos caminos siguen rechazándose (`concurrent-int: firma no soportada`,
   `concurrent-int: areturn no soportado`) y no se produce binario.
3. **El opt-in no es «acepta todo»:** una firma fuera del perfil sigue rechazándose con el mismo mensaje que antes.
4. **La comprobación de clase es defensa, no cobertura:** desde fuente Java type-safe no se puede disparar; no la
   cuentes como un error probado.

Para A: esto elimina la nota de bloqueo de A-04 («el compilador del backend concurrente rechaza cualquier campo no
`final`»). La referencia mutua sigue necesitando `MC_AOT_RAYON_MUTABLE_REFS=1` (§2.3); lo que se abre aquí es el
valor de retorno, no la escritura.

## 3. Clases y operaciones admitidas hoy

`java/util/concurrent/ForkJoinPool` (constructor de 1 y de 4 argumentos con handler `null`), `ForkJoinTask`
(`join`), `Runnable` del proyecto, `java/util/concurrent/atomic/AtomicInteger` (`get`, `getAndIncrement`,
`set`), `java/lang/String` (literal, `hashCode`, `length`, concatenación `(String,int)`),
`java/util/concurrent/CompletableFuture` (`completedFuture`, `new` + `complete`/`isDone`/`getNow`/`get`/`join`
sobre un futuro **ya** completado; pendiente solo en el subperfil de B-03), `TimeUnit` (las siete unidades),
`QuartPos` y las clases del proyecto con el perfil de campos finales `int`/`String`/`Runnable`/`ForkJoinPool`/
`AtomicInteger`/`CompletableFuture`.

Fuera del perfil: subclases y jerarquías, handlers no nulos, factories Java no triviales, interrupción,
`shutdownNow`, callbacks de futuro, `wait`/`notify`, excepciones.

## 4. Opt-ins

| Variable | Efecto | Nota para A |
|---|---|---|
| `MC_AOT_RAYON_MUTABLE_REFS=1` | Admite campos de referencia no `final` (B-09) | Sin él se mantiene el rechazo; ver §2.3 |
| `MC_AOT_FUTURES=restricted` | Habilita el perfil de futuros (completado y pendiente normal) | Nombre canónico desde Q-AB-2; `off` lo apaga y un valor ajeno se rechaza |
| `MC_AOT_FUTURES=completed-only` | Habilita futuros completados y **rechaza** crear uno pendiente | El valor que A ya aceptaba (Q-AB-3); se honra su nombre, no se reinterpreta. El canónico sigue siendo `restricted` |
| `MC_AOT_RAYON_COMPLETED_FUTURE=1` | Alias histórico del anterior | Una versión; sin ninguno de los dos el programa **no se genera** |
| `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` | El mismo concepto en el backend numérico | Dos interruptores para lo mismo: A y B deben unificarlo al integrar |
| `MC_AOT_RAYON_ASSUME_NO_INTERRUPT=1` | Declara que no se modelan interrupciones | Requisito de las rutas de `TracingExecutor` |
| `MC_AOT_RAYON_ASSUME_NO_TRACY=1` | Declara Tracy inactivo | No es soporte de Tracy |

## 5. Fallos: qué ve A

El adaptador no fabrica `Throwable`. Cuando algo no está modelado, devuelve `FrameError` con un mensaje literal
(lista vigente en la §7 del [contrato B-01](futures-contract-b01.md)). Consecuencias prácticas para A:

- Un fallo de tarea **no** se convierte en `ExecutionException`: `join` devuelve `Err` y el generador imprime
  `ejecución concurrent-int: …` y sale con código 2.
- Un envío tras el cierre devuelve `Err("pool cerrado")`, no `RejectedExecutionException`.
- Por tanto A **no puede** escribir código que capture excepciones de concurrencia: debe comprobar el estado
  (por ejemplo `isShutdown`) o dejar que el proceso aborte de forma diagnóstica.

## 6. Decisiones abiertas con A

| Tema | Por qué bloquea | Quién decide |
|---|---|---|
| Representación de `Throwable` | B-03 (fallo de futuro) y B-04 (`get`/`join`) necesitan publicar un fallo como objeto Java | A + B |
| `commonPool()` | Requiere un pool global con identidad compartida entre procesos. **Recomendación de B:** un único pool Rayon global creado perezosamente en el primer `commonPool()`, paralelismo `max(1, available_parallelism-1)` acotado al perfil 1..255, no cerrado por `shutdown()` de pools de usuario, y con el mismo número de procesadores que use A para `Runtime`/`ActiveProcessorCount` | A |
| ~~Un solo opt-in de futuros~~ | **Cerrado en Q-AB-2:** `MC_AOT_FUTURES=restricted` canónico, alias histórico una versión, valor ajeno rechazado | hecho por B y A |
| Callbacks de A dentro de monitores | El adaptador no puede detectar reentrancia hacia el backend principal | A |

## 7. Pruebas de frontera (`mc-aot/tests/rayon_b_api.rs`)

| Prueba | Qué fija |
|---|---|
| `create_accepts_only_the_declared_parallelism` | 1..=255 admitido; 0, negativo y 256 rechazados; sin doble registro |
| `submit_and_join_are_idempotent_and_scoped` | Identidad por tarea, `join` repetido, ids ajenos rechazados |
| `await_termination_is_callers_only` | Un worker no puede esperar su propio cierre; el llamador sí |
| `close_is_idempotent_and_final` | Cierre repetido, envío posterior rechazado, paralelismo conservado |
| `pending_future_published_to_a_worker_is_visible` | Publicación de un futuro pendiente y finalización desde un worker |
| `foreign_heap_references_are_rejected` | Ids y valores de otro heap rechazados |

Ejecutado con Rust 1.99.1 en este entorno: `cargo test --test rayon_b_api` → 34 pruebas, 0 fallos.

## 8. Cómo debe consumirlo A

1. Crear el pool con `create`/`create_with_hooks` cuando el bytecode del backend principal lo pida; no crear
   pools paralelos.
2. Publicar los objetos que las tareas necesitan como `ObjectId` en campos del heap compartido; nunca copiar
   campos a mano ni registrar instancias una por una.
3. Usar `join` solo para tareas propias y esperar desde el llamador; si A necesita esperar desde un worker,
   es una decisión de diseño nueva que hay que acordar aquí.
4. Ante un `Err`, no reintentar ni traducir: registrar el mensaje y dejar que el proceso aborte, salvo que el
   error esté en la lista de rechazos previstos (`pool cerrado`).
