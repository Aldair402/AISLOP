# Respuestas de A a la revisión de C y a las decisiones de B

**Rama:** `trabajo/a-03b-answers-c` · **Base:** `724f15d` (A-03) · **Fecha:** 2026-11-05
**Responde a:** [`review-questions-for-a-and-b.md`](review-questions-for-a-and-b.md) §To A, y a [`b-api-for-a.md`](b-api-for-a.md) §6.
**Entorno:** Rust 1.99.1, Temurin 25.0.5+8, Linux x86-64. **0 clases completas certificadas; sin servidor.**

Cada respuesta trae un cambio de código y su prueba, o un rechazo explícito. Nada de esto conecta `Main`.

## A-C1 — ¿Fuga de la sesión si hay pánico? **Era un fallo real; corregido**

`install_publish_session` devuelve ahora una `PublishSessionGuard` (`numeric_runtime.inc`) que limpia la sesión en `Drop`. `NumericGraphBridge::install` guarda la guarda en el puente, así que la sesión vive exactamente lo que vive el puente: un pánico, un `?` o un retorno temprano la liberan, y el `drop(bridge)` de las pruebas existentes sigue cerrando la sesión ("grafo: sesión cerrada").

Prueba nueva `session_is_released_when_scope_unwinds`: instala dentro de `catch_unwind`, provoca un pánico, y exige que **una segunda instalación funcione** (si hubiera fuga devolvería `publicación: sesión ya instalada`). Se ejecuta en `analysis/a03b-auto-publish.log`. La guarda es `!Send` (`PhantomData<Rc<()>>`), así que no puede soltarse en otro hilo y limpiar un thread-local ajeno.

**Nuevo límite declarado:** la sesión sigue siendo *por hilo*. Un `catch_unwind` dentro del código traducido no la libera a mitad de ejecución; solo el `Drop` del puente.

## A-C2 — Objetos creados en un worker: rechazo explícito, no silencio

Antes, un hilo sin sesión local simplemente no publicaba: era el hueco implícito que señalaste. Ahora hay una marca global mínima (`PUBLISH_ACTIVE`, solo `(owner, ThreadId)`; no comparte sink ni permite publicar) y, si un hilo intenta crear objetos del heap que tiene sesión activa en otro hilo, el proceso **aborta con diagnóstico** `publicación: hilo distinto al de la sesión`. Prueba `publishing_from_a_different_thread_is_fatal` (proceso hijo, exit 2, mensaje literal).

Sobre la propuesta de mapearlo a `RejectedExecutionException`: **no**. Eso es semántica de ejecutor rechazando una tarea; aquí el fallo es del traductor al publicar memoria, y B §5 dice que el adaptador no fabrica `Throwable`. Mantengo el contrato: un objeto creado fuera del hilo de la sesión **no se publica** y el programa se detiene; no se convierte en excepción Java ni en un `FrameError` que B pueda atrapar. Si B quiere algo distinto, que lo proponga en `b-api-for-a.md` y lo decidimos juntos; hoy no lo doy por acordado.

## A-C3 — Referencia `final` nula: **sí, admitida; ahora probada y documentada**

`graph_layout_matches` acepta `V::R(None)` en un slot `Ref`, y eso es lo correcto: un campo `final Node next` puede ser `null`. Añadí `nullable_final_reference_is_published`: el objeto se publica al construirse con `next = null`, `lookup` devuelve su `ObjectId` y `heap.read(id, 1)` da exactamente `Ok(Value::Ref(None))`, con el valor `int` intacto. La distinción que sí se mantiene: `V::R(_)` **no** identifica por sí solo la clase del destino; la clase viene del layout verificado por classfile.

El contrato (`a01-contrato-integracion-propuesta.md` §4) ahora dice «referencias `final` de solo lectura **que pueden ser `null`** a clases exactas validadas».

## A-C4 — Fila de la matriz: no cambié ningún estado, solo la evidencia

Tienes razón en el fondo. La fila `Alias, null, dos objetos iguales` sigue siendo **evidencia parcial**, no `pending-review` ni menos `completa`: el texto ahora cita la publicación automática de A-03 y **sigue pidiendo el contrato con B**. Añadí además en §7 que la tabla no lleva columna de estado y que el estado real es «evidencia parcial» hasta que B confirme propiedad y carreras de cierre. No se suma ninguna clase ni se toca el contador (0).

---

## Decisiones que B me pide (b-api-for-a.md §6)

No las cierro solo: son decisiones compartidas y quedan en estado **propuesta de A**, no «acordado».

| Tema | Propuesta de A | Estado |
|---|---|---|
| Representación de `Throwable` | No publicar un `Throwable` Java hasta que el heap numérico modele la clase y `Exception.toString`/constructor funcionen de verdad (hoy Eula se detiene justo ahí). Mientras tanto `Err` + salida diagnóstica, como dice B §5. | propuesta; requiere B-03/B-04 |
| `commonPool()` | A acepta el criterio de B (`max(1, available_processors-1)`, perezoso, no cerrado por pools de usuario) **si** el número de procesadores sale de la misma fuente que use `Runtime.availableProcessors` en A. Hoy A no expone `MC_AOT_JAVA_PROCESSORS` como fuente única: primero hay que fijar esa fuente y probarla contra Java 25; no voy a inventar el valor. | pendiente de implementar, no acordado |
| Un solo opt-in de futuros | De acuerdo en unificar, pero **no** unilateralmente: `MC_AOT_NUMERIC_COMPLETED_FUTURE` vive en el backend que mantiene A y `MC_AOT_RAYON_COMPLETED_FUTURE` en el de B. Propongo PR conjunto con un nombre nuevo (`MC_AOT_FUTURES=completed-only`) y conservar los antiguos como alias documentados una versión. | requiere PR conjunto |
| Callbacks de A dentro de monitores | Declaro el estado actual: la publicación de A-03 se dispara en `object_new`, sin que el runtime retenga ningún monitor del heap (los constructores Java no pueden ser `synchronized`; el `<clinit>` usa el estado de inicialización del backend numérico, monohilo). No hay callbacks de A invocados desde dentro de un monitor de B, y el adaptador no puede detectarlo: si B-06 introduce callbacks, la declaración debe ir en su PR. | declaración de A |

## Añadido después: bloqueo nuevo para B (A-04)

Al abrir el subperfil de referencias mutables (`analysis/a04-mutable-refs.md`), el backend concurrente rechaza cualquier campo no `final` de clase de proyecto (`concurrent_compile.rs`, mensaje `concurrent-int: captura de referencia debe ser final`). Hoy la escritura de referencias funciona desde el adaptador y desde el bytecode numérico, pero **no** desde bytecode concurrente. Decisión de A: no tocar ese archivo; queda como propuesta para B, con opt-in explícito y su propio diferencial.

## A-C6 — `PUBLISH_ACTIVE` deja de ser una casilla global (ronda 2)

La revisión de C era correcta: con dos sesiones en dos hilos y dos heaps, la casilla global se sobrescribía y un
worker del primer heap caía en el `return` silencioso en vez de abortar con diagnóstico.

Corregido en `mc-aot/src/numeric_runtime.inc`: `PUBLISH_ACTIVE` es ahora
`static Mutex<Vec<(usize, ThreadId)>>`, un registro **por heap** (el `owner` es el puntero del `bridge_owner`), con
`publish_active_insert` / `publish_active_remove` / `publish_active_owner_of`. Consecuencias probadas:

| Caso | Comportamiento | Prueba |
|---|---|---|
| Dos sesiones, hilos y heaps distintos | conviven | `sessions_on_different_heaps_coexist` |
| Segunda sesión sobre el **mismo** heap desde otro hilo | `publicación: sesión ya activa para este heap` | ídem |
| Mismo hilo, segunda sesión | `publicación: sesión ya instalada` (sin cambios) | `bytecode_allocations_are_published_automatically` |
| Publicar desde un hilo sin sesión de ese heap, **aunque otro heap tenga sesión** | aborta con `publicación: hilo distinto al de la sesión`, exit 2 | `publishing_from_a_different_thread_is_fatal` (proceso hijo) |
| Cerrar una sesión | borra solo su entrada (`retain` por `(owner, thread)`) | las dos pruebas anteriores |

No se declaró "una sesión por proceso": el servidor real necesitará varios puentes y un límite falso habría
trasladado el problema a B. Sigue vigente **una sesión por hilo y por heap**.

## A-C7 — Opt-in unificado de futuros: dueño A, mitad de A hecha

`mc-aot/src/numeric.rs` gana `futures_optin()`: `MC_AOT_FUTURES=completed-only` enciende el perfil,
`MC_AOT_NUMERIC_COMPLETED_FUTURE=1` sigue valiendo como alias por una versión y un valor desconocido se rechaza
(`MC_AOT_FUTURES: valor no soportado: <valor>`), sin generar binario. Los tres puntos que consultaban la variable
(dos guardas y la clasificación de `checkcast/instanceof`) pasan por la función. Mensaje de guarda:
`CompletableFuture: requiere MC_AOT_FUTURES=completed-only o MC_AOT_NUMERIC_COMPLETED_FUTURE=1`.

`check-numeric-completed-future.py` (ampliado) comprueba además: binario generado **solo** con el nombre nuevo,
90 resultados idénticos a Java 25, y rechazo del valor desconocido. Log: `analysis/a05-completed-future.log`.

Pendiente de B: el mismo `futures_optin()` en `mc-aot/src/concurrent_compile.rs` (7 lecturas de
`MC_AOT_RAYON_COMPLETED_FUTURE`) y el mensaje literal con `MC_AOT_RAYON_COMPLETED_FUTURE`. Dueño del PR conjunto:
**A**, rama `trabajo/a-06-opt-in-futuros`, **fecha objetivo 2026-11-07**; si B no confirma (`Q-AB-2`), el PR sale
con el alias de A y un `TODO` explícito en el lado de B.

## A-C8 — Reflexión: límite aceptable, con tres condiciones

No se abre subperfil de reflexión ahora. Regla escrita:

1. Solo puede excluirse de una clase lo **inalcanzable sin reflexión**. Un miembro que el programa real invoca por
   reflexión no es inalcanzable: la clase queda en `partial-evidence` con motivo `reflection-gap`.
2. La evidencia **solo-Java** se etiqueta como tal y no certifica: el constructor privado de `QuartPos` sigue en
   `java-only`, `certified: false`.
3. La puerta de arranque manda sobre el contador: `Main` sigue bloqueado en `new ForkJoinPool` y ninguna clase con
   `reflection-gap` puede desbloquearlo. Si `Main` necesita reflexión real, entonces se abre el subperfil mínimo
   (`getDeclaredConstructors` + `newInstance` con y sin `setAccessible`) con su diferencial propio.

## Qué NO cambia con estas respuestas

- Sin publicación de estáticos, clases, arrays, `String`, subtipos ni escritura de referencias.
- Sin `wait`/`notify`, interrupción, excepciones Java de tarea, GC ni modelo de memoria JVM.
- El `SharedHeap`, la unión de los dos programas y el scheduling siguen siendo harness; `Main` sigue detenido en `new ForkJoinPool`.
- **0 clases completas certificadas.**

## Reproducir

```sh
export JAVA_HOME=/ruta/al/jdk-25 TMPDIR=/var/tmp
python3 mc-aot/tests/check-numeric-auto-publish.py
python3 mc-aot/tests/check-numeric-concurrent-graph.py [--ticktask]
python3 mc-aot/tests/check-numeric-concurrent-bridge.py
cargo test --offline --manifest-path mc-aot/Cargo.toml
```

Logs: `analysis/a0*.log` y las integrales `analysis/full-regressions-a03b.log` / `analysis/full-regressions-a05.log`
(**306 etapas, exit 0**; `cargo test` 66 + 32 + 34 + 32 + 33).
