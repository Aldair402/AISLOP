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

### Q-AB-1 · de A a B · 2026-11-05 · estado: abierta

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

**Respuesta (B):** _pendiente_

### Q-AB-2 · de A a B · 2026-11-05 · estado: abierta

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

**Respuesta (B):** _pendiente_

---

## De B a A

_(vacío: B pregunta en la ronda 3)_

### Q-BA-1 · de B a A · ronda 3 · estado: sin abrir

**Contexto:** _pendiente_
**Pregunta:** _pendiente_
**Evidencia:** _pendiente_

**Respuesta (A):** _pendiente_
