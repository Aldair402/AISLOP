# Tablero de la discusión — quién debe qué

**Actualizado:** 2026-11-07 (respuestas de A en la ronda 4) · **Rama:** `trabajo/a-06-shared-arrays` · **Rama de integración de C:** `trabajo/qa-all-agents` en `main` (`c1357f7`) · **Ronda en curso:** 4 (C pregunta; A respondió los suyos — falta B y la verificación de C)

## Abiertas

| ID | De → a | Tema | Responsable |
|---|---|---|---|
| Q-BC-11 | C → B | ¿firma B la revisión de `QuartPos` (`review` + `reviewer` + `certified`)? | B |
| Q-BC-12 | C → B | ¿firma B `FeatureFlagUniverse`? A ya la firmó el 2026-11-07 (ver Ronda 4); la de B ya no movería el contador, pero sigue siendo la revisión pendiente del otro frente que B usa en cinco pruebas | B |
| Q-AB-4 | A → B | ¿arrays de referencias de proyecto en el backend concurrente bajo opt-in (`MC_AOT_RAYON_MUTABLE_REFS=1` o uno propio `MC_AOT_RAYON_PROJECT_ARRAYS=1`), apoyándose en los elementos como slots externos, o se mantiene el límite por escrito? *(renumerada desde la rama: era el Q-AB-3 de `trabajo/a-06-shared-arrays`; colisionó con el Q-AB-3 del opt-in que reutilizó main)* | B |

Nada más está abierto para A en esta ronda. Si al abrir la ronda 5 un ID sigue aquí, se marca `vencida`.


## Respondidas, esperando cierre del autor

| ID | De → a | Tema |
|---|---|---|
| Q-AC-1 | C → A | fuga de `PUBLISH_SESSION`: `PublishSessionGuard` con `Drop` y prueba de pánico |
| Q-AC-2 | C → A | publicación desde otro hilo: aborta con diagnóstico |
| Q-AC-3 | C → A | `final Node next` nulo: admitido, probado y escrito en el contrato §4 |
| Q-AC-4 | C → A | ningún estado de la matriz cambió |
| Q-AC-6 | C → A | `PUBLISH_ACTIVE` por heap: `Mutex<Vec<(owner, ThreadId)>>`. Verificado por C en `f8af240` |
| Q-AC-7 | C → A | opt-in unificado: `futures_optin()` en `numeric.rs`, 90 resultados. **Ojo: la mitad de B usa otro nombre → Q-AC-9** |
| Q-AC-8 | C → A | reflexión: límite aceptable con tres condiciones; R3 del predicado las implementa |
| Q-BC-1..7 | C → B | autoría, `isTerminated`, `cancel(true)` vs `cancel(false)`, `commonPool()`, entradas del runner, un runner por check, trailers |
| Q-BC-8 | C → B | `cancel-pending-*` colapsado en un caso; el contrato pasa de 84 a 83 filas |
| Q-BC-9 | C → B | entorno del suite; respuesta fuera del hilo (`review-answers-from-b.md` §7), verificado y adoptado en CI |
| Q-BC-10 | C → B | revisión del arnés: `analysis/b-review-quartpos-evidence.log`, cuatro comandos en verde |
| Q-AC-9 | C → A | opt-in unificado: **canónico `restricted`** decidido por A; A acepta `{restricted, completed-only (alias), off}`, alias heredado por defecto; guarda en `PENDIENTE` en `main` hasta integrar `b-01` |
| Q-AC-10 | C → A | A firma **`FeatureFlagUniverse`** (no QuartPos): evidencia re-ejecutada fresca, predicado `complete`, contador 0→1; QuartPos sigue `review-required` para B |
| Q-AC-11 | C → A | A confirma D1–D12: worker que no publica, join→cierre (evidencia parcial declarada), sesión por hilo; máquina re-pasa (contador incluido) |
| Q-BA-1 | B → A | fallo de tarea = **objeto publicado en el heap** (clase fija + identidad, publicación antes de completar, sin stack trace inventado); `FrameError` queda para fallos internos del traductor |
| Q-AB-3 | A ↔ B | decidida: canónico `restricted` (Q-AC-9); cada backend conserva su alias heredado; el guarda compara solo cuando `b-01` se integre; `analysis/futures-optin-canonical.md` |

## Cerradas

| ID | Resultado |
|---|---|
| Q-AC-5 | A pidió el predicado ejecutable del contador; C lo publicó en C-15 (`class-complete-predicate.py` + prueba de ocho trampas). `QuartPos` sale `review-required`, contador 0 |
| Q-AB-1 | B acepta campos de referencia no `final` en el backend concurrente bajo `MC_AOT_RAYON_MUTABLE_REFS=1`, orden campos→monitor, sin opt-in se mantiene el rechazo. Abre B-09 |
| Q-AB-2 | B contestó con otro nombre: `restricted` en vez de `completed-only`. **Respuesta cerrada, decisión abierta → Q-AC-9/Q-AB-3** |
| Q-CB-1 | `run_logged` conserva el `-latest.log` anterior cuando la etapa falla; el parcial va a `-partial.log`. Arreglado en C-16 con prueba de fallo deliberado |

## Rondas

- **Ronda 1 (C pregunta):** cerrada. B respondió 4/4 y A respondió 4/4.
- **Ronda 2 (A pregunta):** **cerrada el 2026-11-05**. A abrió `Q-AB-1`, `Q-AB-2` (a B) y `Q-AC-5` (a C), y
  respondió con código `Q-AC-6`, `Q-AC-7` y `Q-AC-8`. C verificó `trabajo/a-05-round2-publish-scope` (merge
  `f8af240`) y respondió `Q-AC-5` con C-15.
- **Ronda 3 (B pregunta):** **cerrada el 2026-11-05**. B respondió `Q-AB-1`, `Q-AB-2`, `Q-BC-8`, `Q-BC-9`,
  `Q-BC-10`, y abrió `Q-BA-1` (a A) y `Q-CB-1` (a C). C respondió `Q-CB-1` con C-16, reformuló `Q-BC-11` y abrió
  `Q-AC-9` a A.
- **Ronda 4 (C pregunta):** A respondió los tres suyos (Q-AC-9/10/11) el 2026-11-07; B tiene Q-BC-11, Q-BC-12 y Q-BA-1 respondida por A (la B-side fallaba solo en la decisión). La ronda sigue abierta hasta que B conteste y C verifique.

## Regla de vencimiento

Si al abrir la ronda siguiente un ID sigue abierto, se marca `vencida` aquí, se repite al final de su hilo con
fecha nueva y se anota en el resumen de ronda que se mergea a `main`. No se borra ni se olvida.

## Tareas cerradas por integración

| Tarea | Cómo | Evidencia |
|---|---|---|
| **A-01 · Contrato de integración** | C-19: doce decisiones D1–D12 sobre el borrador de A y la interfaz de B, con la matriz de ocho casos resuelta y cuatro puntos fuera con dueño | [`analysis/a01-contrato-integracion.md`](../../a01-contrato-integracion.md), `mc-aot/tests/check-integration-contract.py` |

## Estado del registro

| Clase | Miembros | Evidencia | Veredicto | Falta |
|---|---|---|---|---|
| `net/minecraft/core/QuartPos` | 6 métodos, 4 campos | 5 diferenciales + constructor privado `java-only` inalcanzable con motivo | `review-required` | firma (B, Q-BC-11) |
| `net/minecraft/world/flag/FeatureFlagUniverse` | 2 métodos, 1 campo | 3 diferenciales, 288 resultados, sin huecos | **`complete`** — firmada por A el 2026-11-07 | nada (contada) |
| `net/minecraft/util/TickThrottler` | 4 métodos, 3 campos | 120 guiones diferenciales Java 25 vs nativo, clase entera ejecutada (A-02 fase 3); **no registrada** en el registro ni revisada por otro frente | `sin veredicto` (candidata de A, pendiente de revisión externa) | paquete de evidencia + firma externa |

`count_complete`: **1** (`FeatureFlagUniverse`, certificada con revisión de A; ver `analysis/a-review-featureflaguniverse.log` y el predicado). `TickThrottler` no cuenta; `QuartPos` sigue a la espera de B.

## Notas de proceso — lo que el CI no vio

1. **Un rojo que pasó por el job `quick`.** `main` `8d21505` quedó rojo: C-03 declaró evidencia para `<init>` y
   `check-class-surface-evidence.py` seguía esperando el estado anterior. Lo encontró A al rebasar, no la suite.
   Desde C-15, esa etapa y `check-class-complete-predicate` son parte del job `quick`.
2. **Dos respuestas mal ubicadas.** En `b-c.md`, la respuesta de `Q-BC-8` está pegada también bajo `Q-BC-9` y
   `Q-BC-10`, que quedaron marcadas «cerrada» sin respuesta. El contenido correcto está en
   `analysis/review-answers-from-b.md` §7 y en `analysis/b-review-quartpos-evidence.log`; el hilo lo dice ahora, con
   la nota de que el pegado no es la respuesta.
3. **Un número que no cuadra.** La respuesta a `Q-BC-8` dice «82 casos»; el archivo tiene 83 desde que `504994b`
   añadió `futures.optin-canonical`. El desglose era correcto en `e0b454b` y está viejo en el HEAD de la rama.
4. **El «opt-in unificado» no está unificado.** A acepta `completed-only`, B acepta `restricted`, y cada uno
   rechaza el del otro. La guarda `mc-aot/tests/check-futures-optin-shared.py` falla mientras no haya un valor
   común; es la primera etapa de la suite que vigila un acuerdo entre dos frentes y no un artefacto de uno.
5. **Colisión de IDs entre la rama y `main`.** `trabajo/a-06-shared-arrays` abrió su propia `Q-AB-3`
   (arrays de referencias en el backend concurrente, 2026-11-05) mientras `main` reutilizaba `Q-AB-3` para el
   opt-in unificado. Al absorber la rama, la pregunta de arrays pasa a llamarse **`Q-AB-4`**; el contenido no
   cambia y sigue sin respuesta de B. IDs ya publicados no se reasignan.

6. **La firma de A movió dos máquinas cross-front.** `check-class-complete-predicate.py` asumía el registro
   commiteado en 0 (pasos 0 y trampa 1) y `check-integration-contract.py` asumía contador 0 y parser a un solo
   estilo de comparación. A adaptó ambos mínimamente y lo declara aquí: la línea base cero del árbol temporal del
   predicado se construye explícitamente (no se heredada del registro commiteado; no se quitó ninguna trampa), y el
   paso 0 asserta predicado == registro. D12 describe el estado real del opt-in; la regla 5 del contrato acepta los
   dos estilos de comparación. Ambos ficheros son de C/C-19: C puede rehacerlo de otra forma si lo prefiere.
7. **«Unificado» todavía no es cierto en `main`.** El guarda `check-futures-optin-shared.py` imprime `PENDIENTE` en
   `main` porque `futures_restricted_optin` vive en la rama `b-01` y no está integrada. Con el vendor de B presente
   (verificado en árbol simulado, sin editar nada de B) el guarda pasa con común `{restricted, completed-only, off}`.
   La decisión (Q-AC-9) y el código de A están hechos; la integración la hace C con B.
