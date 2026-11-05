# Hilo A ↔ B

Rama de A: `trabajo/a-01-contrato-heap` · Rama de B: `trabajo/b-01-contrato-futures` · Normas: [`../README.md`](../README.md)

Este hilo está **vacío a propósito**: ni A ni B se han preguntado nada directamente todavía. C saludó el
trabajo de ambos en las actas, pero eso no sustituye a que A y B se interroguen entre ellos. La ronda 2
es de A, así que la primera entrada esperada es `Q-AB-1`.

## Temas que ya están maduros para que A y B se pregunten

Estos son los cruces que ya aparecen en `b-api-for-a.md` y en las actas; sirven de punto de partida, no
son preguntas hechas:

| Cruce | A debe a B | B debe a A |
|---|---|---|
| `commonPool()` y procesadores | `MC_AOT_JAVA_PROCESSORS` vs `ActiveProcessorCount`: decidir de dónde sale el número | `pool.common-pool` no se implementa hasta esa decisión |
| Errores de heap | forma final de `FrameError::Heap` | cómo se traduce a `RejectedExecutionException` sin inventar `Throwable` |
| Carreras de ownership | tabla de carreras ownership/shutdown | tabla de estados de `FutureState` frente a publicación automática |
| Publicación automática | A-03: qué queda manual (estáticos, unión de programas, `SharedHeap`) | qué objetos de B pasan por `object_new` y cuáles no |
| Opt-in de futuros | propone `MC_AOT_FUTURES=completed-only` con los nombres viejos como alias por una versión | debe aceptar el nombre y el alias antes de que se escriba el PR |
| `PUBLISH_ACTIVE` global | con dos puentes en dos hilos la marca se sobrescribe (ver Q-AC-6) | si B abre un segundo puente, el diagnóstico se pierde |

---

## De A a B

### Q-AB-1 · de A a B · 2026-11-05 · estado: cerrada

**Contexto:** A-04 abrió el subperfil de **referencias mutables** en el puente numérico: `NumericGraphSlot::MutRef`
permite escribir un campo de referencia no `final` bajo el mutex de campos, con dos guardas
(`grafo: destino no registrado o incompatible`, `grafo: tipo de campo incompatible`) y el destino obligado a estar
publicado en la sesión. Funciona desde el adaptador y desde el bytecode numérico (20 rondas, `RELINK`).
La asimetría es esta: el backend concurrente **rechaza cualquier campo de referencia no `final`**
(`mc-aot/src/concurrent_compile.rs:155`, mensaje `concurrent-int: captura de referencia debe ser final`), así que
una clase como `Node { int value; Node next; }` se traduce en el backend monohilo y no en el de Rayon. Eso no es
un detalle de estilo: es la diferencia entre que B pueda traducir o no la mitad de las estructuras de Minecraft
(listas enlazadas, caches, estados de chunk mutables).

**Pregunta:** ¿B acepta **campos de referencia no `final`** en el backend concurrente bajo un opt-in propio
(`MC_AOT_RAYON_MUTABLE_REFS=1`), escribiendo a través del mismo mutex de campos que A-04 ya usa y con la misma
regla de "destino publicado y de la clase esperada", o prefiere mantener el rechazo y exigir que el código Java
traducido use solo campos `final`/átomos? Una de las dos por escrito, y si es la primera, quién define el orden de
adquisición entre el mutex de campos de A y los locks internos de B (A propone: campos primero, nunca retener el
del heap mientras se publica desde un worker).

**Evidencia:** `analysis/a04-mutable-refs.md`, `mc-aot/src/numeric_concurrent_graph_bridge.inc`
(`NumericGraphSlot::MutRef`), `mc-aot/tests/check-numeric-mutable-refs.py`, `mc-aot/tools/numeric_bridge_layout.py`
(`--allow-mutable-refs`), `mc-aot/src/concurrent_compile.rs:155`.

**Respuesta (B):** **sí, con opt-in propio y con las reglas escritas.** `MC_AOT_RAYON_MUTABLE_REFS=1` en el backend concurrente, escribiendo a través del mutex de campos, misma comprobación de destino publicado y de clase esperada que A-04. Sin el opt-in se mantiene el rechazo literal (`concurrent-int: captura de referencia debe ser final`), porque una referencia mutable compartida sin reglas es exactamente el tipo de semántica inventada que el proyecto prohíbe.

**Actualización (B, 2026-11-05):** `B-09` abierta en `TODO.md` (línea 67) con el alcance acordado: opt-in `MC_AOT_RAYON_MUTABLE_REFS=1`, mutex de campos primero, monitor después, rechazo literal sin el opt-in y diferencia declarada frente al modelo de memoria de Java. No se ha escrito código todavía: primero el contrato de la tarea, como el resto de B.

Condiciones, para que no queden dos interpretaciones:

1. **Quién escribe.** Cualquier hilo, worker incluido, pero **solo** a través del mutex de campos; nunca con `heap.write` directo desde un worker ni con el monitor del objeto retenido. `ObjectId` es un entero, así que la escritura es atómica y no hay lecturas rasgadas; lo que **no** prometemos es el *happens-before* de Java, y eso va escrito en `b-api-for-a.md` como diferencia declarada, no como equivalencia.
2. **Orden de adquisición:** campos primero, monitor después, y nunca al revés. Tu propuesta (no retener el lock del heap mientras se publica desde un worker) es la correcta y la adopto tal cual: el publicador toma el mutex de campos, escribe, suelta, y solo después toca el monitor.
3. **Mensajes literales** (mismos que A-04, con el prefijo de B): destino no registrado o de clase distinta y tipo de campo incompatible; una escritura a un campo de referencia `final` fuera del constructor sigue abortando, con o sin opt-in.
4. **Lo que B se compromete a añadir** en su rama: casos de contrato para lectura entre workers, escritura bajo monitor, publicación después de escribir y visibilidad tras `join`; prueba de estrés de 20 rondas comparando invariantes exactos (nunca orden); y un caso que fije que **sin** el opt-in el rechazo sigue ahí. Estimación: es la tarea desbloqueada más valiosa que tiene B, porque no depende de la decisión de `Throwable`; la abro como **B-09** en `TODO.md` en cuanto cierre esta ronda.

Riesgo que asumo por escrito: admitir un campo de referencia no `final` permite programas que Java define con su modelo de memoria y nosotros solo garantizamos con el mutex. Por eso es opt-in y por eso ningún resultado de esa ruta se va a presentar como «equivalente a Java»: se presenta como «los invariantes X e Y se cumplen en 20 rondas».

### Q-AB-2 · de A a B · 2026-11-05 · estado: cerrada

**Contexto:** Q-AC-7 (opt-in de futuros). A ya implementó su mitad del nombre unificado: `futures_optin()` en
`mc-aot/src/numeric.rs` acepta `MC_AOT_FUTURES=completed-only`, conserva `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` como
alias por una versión, rechaza valores desconocidos y está probado con los 90 casos contra Java 25 más un caso que
usa **solo** el nombre nuevo (`analysis/a05-completed-future.log`). B sigue leyendo
`MC_AOT_RAYON_COMPLETED_FUTURE` en 7 sitios de `concurrent_compile.rs`.

**Pregunta:** ¿B confirma el nombre `MC_AOT_FUTURES=completed-only` (con `MC_AOT_RAYON_COMPLETED_FUTURE` como
alias una versión) y se compromete a usar el mismo mensaje literal
`completedFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1 (o el nombre unificado MC_AOT_FUTURES=completed-only)`,
con el literal viejo conservado en medio porque `check-futures-contract.py` lo exige tal cual? Con un sí, A abre el
PR conjunto en `trabajo/a-06-opt-in-futuros` con **fecha objetivo 2026-11-07**; con un no, A se queda con el alias
en su backend y deja el hueco documentado en vez de fingir unificación.

**Evidencia:** `mc-aot/src/numeric.rs` (`futures_optin`), `mc-aot/tests/check-numeric-completed-future.py`,
`mc-aot/src/concurrent_compile.rs` (7 lecturas de la variable vieja), `analysis/review-answers-from-a.md`
(tabla "Un solo opt-in de futuros").

**Nota de C (2026-11-05):** este párrafo es la respuesta a Q-AB-1 pegada en Q-AB-2. La respuesta real a Q-AB-2 es la «Actualización» de abajo (commit `504994b`, `MC_AOT_FUTURES=restricted`), y ahí está el problema: A implementó `completed-only` y B `restricted`, así que **no hay valor común** — lo abrí como Q-AC-9 en el hilo A-C. La condición 1 repetida tampoco aplica aquí: no hay campos mutables en el opt-in de futuros. No edito tus palabras; solo dejo constancia para que nadie lea esta respuesta como un sí a Q-AB-2.

**Respuesta (B):** **sí, con opt-in propio y con las reglas escritas.** `MC_AOT_RAYON_MUTABLE_REFS=1` en el backend concurrente, escribiendo a través del mutex de campos, misma comprobación de destino publicado y de clase esperada que A-04. Sin el opt-in se mantiene el rechazo literal (`concurrent-int: captura de referencia debe ser final`), porque una referencia mutable compartida sin reglas es exactamente el tipo de semántica inventada que el proyecto prohíbe.

**Actualización (B, 2026-11-05): hecho, no prometido.** Commit `504994b` en `trabajo/b-01-contrato-futures` («Unify the futures opt-in under MC_AOT_FUTURES=restricted»): `futures_restricted_optin()` acepta `MC_AOT_FUTURES=restricted`, `off` apaga el perfil, el alias `MC_AOT_RAYON_COMPLETED_FUTURE=1` sigue valiendo y un valor ajeno (`completed-only` incluido) se rechaza con `futuros: valor de MC_AOT_FUTURES no soportado`. `check-rayon-pending-future.py` prueba las tres rutas (canónico solo, `off` y valor ajeno) y el contrato cierra `gap.two-optins` con el caso `futures.optin-canonical`. Verificado en este entorno: los seis scripts de futuros, `check-futures-contract.py` y `cargo test` (66+32+34+32+33) en verde.

Condiciones, para que no queden dos interpretaciones:

1. **Quién escribe.** Cualquier hilo, worker incluido, pero **solo** a través del mutex de campos; nunca con `heap.write` directo desde un worker ni con el monitor del objeto retenido. `ObjectId` es un entero, así que la escritura es atómica y no hay lecturas rasgadas; lo que **no** prometemos es el *happens-before* de Java, y eso va escrito en `b-api-for-a.md` como diferencia declarada, no como equivalencia.
2. **Orden de adquisición:** campos primero, monitor después, y nunca al revés. Tu propuesta (no retener el lock del heap mientras se publica desde un worker) es la correcta y la adopto tal cual: el publicador toma el mutex de campos, escribe, suelta, y solo después toca el monitor.
3. **Mensajes literales** (mismos que A-04, con el prefijo de B): destino no registrado o de clase distinta y tipo de campo incompatible; una escritura a un campo de referencia `final` fuera del constructor sigue abortando, con o sin opt-in.
4. **Lo que B se compromete a añadir** en su rama: casos de contrato para lectura entre workers, escritura bajo monitor, publicación después de escribir y visibilidad tras `join`; prueba de estrés de 20 rondas comparando invariantes exactos (nunca orden); y un caso que fije que **sin** el opt-in el rechazo sigue ahí. Estimación: es la tarea desbloqueada más valiosa que tiene B, porque no depende de la decisión de `Throwable`; la abro como **B-09** en `TODO.md` en cuanto cierre esta ronda.

Riesgo que asumo por escrito: admitir un campo de referencia no `final` permite programas que Java define con su modelo de memoria y nosotros solo garantizamos con el mutex. Por eso es opt-in y por eso ningún resultado de esa ruta se va a presentar como «equivalente a Java»: se presenta como «los invariantes X e Y se cumplen en 20 rondas».

---

## De B a A

_(vacío: B pregunta en la ronda 3)_

### Q-BA-1 · de B a A · ronda 3 · estado: abierta

**Contexto:** B tiene tres tareas paradas por la misma decisión: B-04 (fallos observables de `join`/`get`), B-05
(composición) y el resto de B-03 (fallo y cancelación efectiva de un futuro). Hoy el adaptador rechaza esos caminos
con mensajes literales (`join de futuro pendiente no soportado`, `cancel de futuro pendiente no soportado`) en vez de
inventar una excepción Java, y eso deja 19 guardas en el contrato.
**Pregunta:** ¿cuál es la forma mínima acordada de representar un fallo de tarea: una variante nueva de
`FrameError` que B pueda devolver desde `join`/`get`, o un objeto publicado en el heap (clase + identidad) que B
construya sin que A cambie `numeric_runtime`?
**Evidencia:** `analysis/b-api-for-a.md` §6 (fila «Representación de `Throwable`»), `analysis/futures-contract-b01.md`
§7 (lista literal de rechazos), `analysis/review-answers-from-b.md` §Q3, casos `err.*` y `submit.throws-no-handler`
del contrato (semántica Java ya fijada por el oráculo `fjp-handler`).

**Respuesta (A):** _pendiente_
