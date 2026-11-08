# A-01 — Contrato de integración entre el backend numérico y el concurrente

**Estado: CERRADO (contrato decidido y comprobado por máquina).** Cierra la tarea A-01 de [`TODO.md`](../TODO.md).
**Base:** `main` `70dfca4` · **Fecha:** 2026-11-05 · **Cierre por:** frente C en su papel de integración (C-08), a
partir del borrador de A (`a01-contrato-integracion-propuesta.md`), de la interfaz de B
(`b-api-for-a.md`, B-07) y del contrato de futuros de B (`futures-contract-b01.md`, B-01 §7).

El borrador de A terminaba en «**pendiente de B**: mecanismo concreto de publicación, propiedad de la sesión
durante tareas, orden de shutdown y forma de indicar cancelación o fallos. A-01 no se cierra hasta acordarlo y
revisar casos de carrera». Esos cuatro puntos ya tienen respuesta escrita y prueba ejecutable en ambos frentes.
Lo que sigue es la decisión, con la evidencia al lado; **no hay una sola decisión nueva de C**: cada D* elige una
de las dos propuestas que ya estaban sobre la mesa, o deja el punto abierto con dueño y nombre.

> **Qué significa «cerrado» aquí.** El *contrato* está cerrado: la frontera entre los dos backends está decidida y
> `mc-aot/tests/check-integration-contract.py` falla si el código o estos documentos dejan de cumplirla. **No**
> significa que A-05, A-06, A-07, B-05 o B-06 estén hechos: son implementación, y siguen abiertos con su dueño en
> la §4.

---

## 1. La frontera, en una línea

```
bytecode Java ──(backend numérico, A)──┐
                                       ├── ObjectId(int) + SharedHeap ──(Rayon, B)
harness/fixture ───────────────────────┘
```

Lo único que cruza es un `ObjectId` **válido solo en su `SharedHeap`**. No hay traducción de identificadores, no
hay copia implícita de campos, no hay un segundo heap. Todo lo demás —quién publica, cuándo, con qué lock y qué
mensaje sale cuando algo no está modelado— es lo que fijan las decisiones D1–D12.

## 2. Decisiones

| id | Decisión | Evidencia en código | Prueba que la fija |
|---|---|---|---|
| D1 | **Identidad.** Un `ObjectId` solo es válido en su heap; el índice numérico nunca se interpreta como `ObjectId` ajeno. La sesión se identifica por `Heap.bridge_owner`. | `concurrent_heap.rs` (`store.check(id)`), `numeric_runtime.inc:288` (`bridge_owner`), `numeric_concurrent_graph_bridge.inc:66` (`grafo: otro heap numérico`) | `rayon_b_api.rs::foreign_heap_references_are_rejected`, `check-numeric-concurrent-graph.py` |
| D2 | **Biyectividad.** En una sesión, `(dueño, índice)` ↔ `(SharedHeap, ObjectId)` es biyectivo para lo registrado; dos referencias al mismo objeto dan el mismo ID y dos objetos distintos no se confunden aunque tengan campos iguales. `null` = `None`, no se registra. | `numeric_concurrent_graph_bridge.inc` (`forward`/`alive`, `grafo: identidad inconsistente`) | `check-numeric-concurrent-graph.py` (alias y nulos) |
| D3 | **Publicación.** Publicar = entregar el `ObjectId`; el objeto **no** se copia. El backend numérico registra al construir (`object_new` → `PublishSink`), no enumerando instancias a mano. Un objeto que el sink no admite no se publica y el programa sigue: no es un error. | `numeric_runtime.inc` (`install_publish_session`, `publish_new_object`, `if !sink.admits(class){return;}`) | `check-numeric-auto-publish.py` |
| D4 | **Sesión por hilo y por heap.** Hay una sesión de publicación por hilo; dos heaps distintos pueden tener sesión a la vez, el mismo heap dos veces no. La guarda la libera en `Drop` (retorno o pánico). | `numeric_runtime.inc:920-960` (`PUBLISH_ACTIVE: Mutex<Vec<(usize, ThreadId)>>`, `PublishSessionGuard`) | `check-numeric-auto-publish.py` (sesión duplicada rechazada, segundas sesiones activas) |
| D5 | **Un worker no publica.** Publicar desde un hilo distinto al de la sesión aborta con diagnóstico (`publicación: hilo distinto al de la sesión`) y **no** se convierte en excepción Java. | `numeric_runtime.inc` (`publish_new_object`) | `check-numeric-auto-publish.py` |
| D6 | **Publicar antes de completar.** Un futuro pendiente puede publicarse en un campo `final` de otra clase y completarse después desde un worker; eso es exactamente el caso de A-06 y está admitido. | `concurrent_heap.rs` (`mark_pending_future`, `future_complete`) | `rayon_b_api.rs::pending_future_published_to_a_worker_is_visible` |
| D7 | **Orden de locks.** Nunca se retiene el lock del heap/tabla mientras se entra al adaptador, se espera un monitor o se ejecuta código. Al leer una referencia: se copia el valor bajo el lock de campos, se **suelta**, y solo después se toma el lock del mapa de identidad. Nunca los dos a la vez. | `concurrent_heap.rs` (`drop(store)` antes de `external.*` en `read`/`write`/`enter`), `numeric_concurrent_graph_bridge.inc:32-37` (bloque acotado para el valor, mapa después) | comprobación estructural en `check-integration-contract.py` + `check-numeric-concurrent-graph.py` |
| D8 | **Monitores.** Un único monitor reentrante por objeto, el mismo para los dos backends; se adquiere y libera por el mismo hilo; ninguna ruta adquiere el monitor conservando el lock de campos. | `concurrent_heap.rs` (`enter` → `MonitorGuard::{Local,External}`) | `rayon_b_api.rs`, `check-monitors` (suite) |
| D9 | **Shutdown.** `shutdown()` **no** espera a las tareas en curso; `isTerminated` es `false` mientras corren; `awaitTermination` solo desde el llamador, nunca desde un worker del mismo pool. Cerrar la sesión exige haber esperado antes a las tareas: el orden es *join/await → cerrar sesión*. | `executor_runtime.rs` (`shutdown`, `await_termination`, `is_terminated`) | `rayon_b_api.rs::await_termination_is_callers_only`, `close_is_idempotent_and_final` |
| D10 | **Fallos.** No se fabrica `Throwable`. Un fallo de tarea devuelve `Err` con mensaje literal; el proceso aborta con diagnóstico (`ejecución concurrent-int`, código 2). A **no** captura excepciones de concurrencia: consulta estado o deja abortar. Cancelación es **guarda**, no implementación: `cancel de futuro pendiente no soportado` para las dos banderas. | `executor_runtime.rs`, `concurrent_heap.rs` | `check-futures-contract.py` (B-01 §7), `check-rayon-pending-future.py` |
| D11 | **Campos.** El layout sale del classfile, no de la etiqueta `V::I`. Primer perfil: campos `int` no `final`/no `volatile` y referencias `final` de solo lectura que pueden ser `null` a clases exactas validadas. `int final` se rechaza (el puente no distingue final por slot). Referencias mutables solo bajo `MC_AOT_RAYON_MUTABLE_REFS=1`, con orden campos→monitor. | `concurrent_compile.rs:155`, `numeric_concurrent_graph_bridge.inc` (`NumericGraphSlot::MutRef`), `numeric_bridge_layout.py --allow-mutable-refs` | `check-numeric-mutable-refs.py` (registrada en la suite por este cierre), `check-numeric-bridge-layout.py` |
| D12 | **Un solo opt-in de futuros.** Regla: una variable canónica, nombres actuales como alias por una versión, valor desconocido **rechazado** (no adivinado). **Decidido el 2026-11-07 (Q-AC-9/Q-AB-3, con la respuesta de B en Q-AB-2): el canónico es `restricted`** — el que B honra en su `futures_restricted_optin()` desde `504994b` y el que describe el perfil con precisión. A acepta `{restricted, completed-only}` (este último como alias histórico por una versión) y `off` lo apaga; `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` sigue como alias heredado. B acepta el mismo conjunto. La mitad de B **no está integrada en `main`** (rama `b-01`); el guarda `check-futures-optin-shared.py` dice `PENDIENTE` en `main` y pasa con el vendor de B presente (verificado en un árbol simulado, ver `analysis/futures-optin-canonical.md`). | `numeric.rs` (`futures_optin`), `concurrent_compile.rs` (rama `b-01`) | `check-futures-optin-shared.py` (dice `PENDIENTE` en `main` porque B-01 no está integrada; pasa con la rama de B presente) |

### 2.1 Superficie de rechazo (mensajes literales)

Cada uno de estos mensajes existe hoy en `mc-aot/src` y `check-integration-contract.py` lo verifica. Un rechazo
declarado **no** es una equivalencia con Java: es lo que el perfil dice que no modela.

```text
grafo: otro heap numérico                                  (D1  índice/heap ajeno)
grafo: identidad inconsistente                             (D2  alias o dos referencias al mismo objeto)
grafo: destino no registrado o incompatible                (D2  leer una referencia cuyo destino no está)
grafo: tipo de campo incompatible                          (D11 tipo distinto del declarado)
publicación: sesión ya instalada                           (D4  dos sesiones en el mismo hilo)
publicación: sesión ya activa para este heap               (D4  dos sesiones sobre el mismo heap)
publicación: hilo distinto al de la sesión                 (D5  un worker intenta publicar)
captura de referencia debe ser final                       (D11 referencia no final sin opt-in)
pool cerrado                                               (D9  envío tras shutdown)
awaitTermination desde worker propio no soportado          (D9  autobloqueo de un worker)
cancel de futuro pendiente no soportado                    (D10 cancelación no modelada)
```

## 3. La matriz del borrador, resuelta

| Caso (borrador §7) | Resolución | Estado |
|---|---|---|
| Alias, null, dos objetos iguales | D1 + D2. Evidencia parcial → evidencia con alias y nulos en el fixture de grafo y en el heap de B | **decidido y probado** |
| Heap ajeno, doble sesión y cierre | D1 + D4 + D9. Rechazo explícito; cierre = *join/await → cerrar* | **decidido y probado** |
| Autoalias y ciclo de referencias | D2. Se registran todos los nodos antes de publicar; el mapa es la autoridad | **decidido**; falta prueba de ciclo largo (A-05) |
| Tipo/`final`/`volatile` o hash alterado | D11. Se rechaza antes de publicar/generar; el classfile manda | **decidido y probado** |
| Monitor reentrante, contención y unwind | D8. Un solo monitor; la guarda libera en `Drop` | **decidido y probado** |
| Tarea falla o `join` espera | D10. `Err` + literal, nunca `ExecutionException`; `join` idempotente | **decidido y probado** |
| Estáticos y `<clinit>` | Fuera del contrato: no se unen. Se rechazan, no se finge soporte | **abierto con dueño (A-05)** |
| `Main`/`Util.makeExecutor` | Fuera: A-07/B-06. El contrato no afirma que la ruta real funcione | **abierto con dueño (A-07, B-06)** |

## 4. Lo que queda fuera de A-01, con dueño

| Tema | Dueño | Por qué no bloquea el contrato |
|---|---|---|
| Representación de `Throwable` (fallo de tarea como objeto Java) | A + B (`Q-BA-1`) | D10 ya fija **qué no** se hace: hoy no hay excepción. Cuando se decida, entra como decisión nueva, no como reinterpretación de esta |
| `commonPool()` perezoso y número de procesadores | A | El contrato no lo menciona; B ya dio recomendación escrita |
| Valor canónico de `MC_AOT_FUTURES` | A + B (`Q-AC-9`, `Q-AB-3`) | D12 fija la **regla** (una variable, alias, rechazo de lo desconocido); el literal no cambia ninguna frontera de datos |
| Estáticos, `<clinit>`, unión de programas | A-05 | Sin `<clinit>` no hay inicialización que compartir; el primer perfil lo excluye explícitamente |
| `Main` y `Util.makeExecutor` de punta a punta | A-07, B-06 | Requiere la ruta real; afirmarlo sin ejecutarla es lo que el proyecto prohíbe |

## 5. Cómo se comprueba

`mc-aot/tests/check-integration-contract.py` verifica contra el código, no contra la prosa:

1. **Literales**: cada mensaje de rechazo citado en este documento existe en `mc-aot/src` (substring exacto).
2. **Símbolos**: cada función nombrada existe en el archivo que se dice (`Executors::create|join|await_termination|shutdown|is_terminated|parallelism` en `executor_runtime.rs`; `read|write|enter|mark_pending_future|future_complete` en `concurrent_heap.rs`; `install_publish_session|publish_active_insert|publish_active_owner_of` en `numeric_runtime.inc`).
3. **Locks (D7/D8)**: ninguna línea del puente de grafo toma `fields.lock()` y `map.lock()` a la vez; `read`/`write`/`enter` sueltan el lock de la tabla (`drop(store)`) antes de delegar en un objeto externo; `MonitorGuard` existe con las dos variantes.
4. **Pruebas citadas**: las seis pruebas de frontera de B existen por nombre en `rayon_b_api.rs`, y las de A (`check-numeric-concurrent-graph.py`, `check-numeric-auto-publish.py`, `check-numeric-mutable-refs.py`) existen **y** están registradas en `run-regressions.sh`.
5. **D12 sin mentira**: si los dos backends pasan a compartir un valor, o si dejan de existir los dos nombres, esta comprobación falla y obliga a actualizar D12 — el contrato no puede quedarse describiendo una divergencia que ya no existe, ni al revés.
6. **Nada certifica**: `count_complete` sigue en 0 y ninguna clase del registro está certificada por este documento.

Lo que **no** comprueba: que el orden de locks sea correcto en *todas* las rutas (solo detecta el patrón prohibido en los archivos citados); que no haya interbloqueos; el modelo de memoria JVM. Eso lo dicen las pruebas con timeout, no un `grep`.

## 6. Qué cambia respecto del borrador

- El borrador decía «no se permite cerrar mientras haya operaciones concurrentes sin definir y probar ese protocolo». D9 lo define: `shutdown` no espera, `awaitTermination` es del llamador, y el cierre de sesión va **después** del join.
- El borrador dejaba «mecanismo concreto de publicación» a B. D3/D4/D5 lo fijan con el código de A-03, no con una promesa.
- El borrador proponía «campo de referencia `final` de solo lectura»; D11 añade el subperfil opt-in de referencias mutables de A-04, con su orden de locks, porque ya existe y está probado.
- El borrador no hablaba de opt-ins. D12 los mete en el contrato, incluida la divergencia que había (resuelta el 2026-11-07 con la decisión del canónico `restricted`); el hueco se documenta, no se tapa.

**Sin cambios de código de A ni de B.** Este cierre es de decisión y de verificación; lo único que toca la
infraestructura es registrar `check-numeric-mutable-refs.py` en la integral, que no estaba.
