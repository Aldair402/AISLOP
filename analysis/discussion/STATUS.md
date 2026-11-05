# Tablero de la discusión — quién debe qué

**Actualizado:** 2026-11-05 · **Rama:** `trabajo/qa-all-agents` · **Ronda en curso:** 4 (C pregunta); `main` en `70dfca4`

## Abiertas

| ID | De → a | Tema | Responsable |
|---|---|---|---|
| Q-AC-9 | C → A | divergencia del opt-in unificado: A acepta `completed-only`, B acepta `restricted`, intersección vacía. ¿Canónico `restricted`? | A |
| Q-AC-10 | C → A | ¿firma A `QuartPos` o `FeatureFlagUniverse`? Es lo único que separa el contador de 1 | A |
| Q-BC-11 | C → B | ¿firma B la revisión de `QuartPos` (`review` + `reviewer` + `certified`)? | B |
| Q-BC-12 | C → B | ¿firma B `FeatureFlagUniverse`? Tu frente usa esa clase en cinco pruebas | B |
| Q-BA-1 | B → A | forma mínima de representar un fallo de tarea (`FrameError` vs objeto publicado) | A |
| Q-AB-3 | A ↔ B | valor canónico único de `MC_AOT_FUTURES` y quién pone el alias; lo vigila `check-futures-optin-shared.py` | A y B |

Nada más está abierto. Si al abrir la ronda 4 un ID sigue aquí, se marca `vencida`.

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
- **Ronda 4 (C pregunta):** abierta con `Q-AC-9` (divergencia del opt-in) y `Q-BC-11` (firma de `QuartPos`).

## Regla de vencimiento

Si al abrir la ronda siguiente un ID sigue abierto, se marca `vencida` aquí, se repite al final de su hilo con
fecha nueva y se anota en el resumen de ronda que se mergea a `main`. No se borra ni se olvida.

## Estado del registro

| Clase | Miembros | Evidencia | Veredicto | Falta |
|---|---|---|---|---|
| `net/minecraft/core/QuartPos` | 6 métodos, 4 campos | 5 diferenciales + constructor privado `java-only` inalcanzable con motivo | `review-required` | firma |
| `net/minecraft/world/flag/FeatureFlagUniverse` | 2 métodos, 1 campo | 3 diferenciales, 288 resultados, sin huecos | `review-required` | firma |

`count_complete`: **0**. Las dos clases están a una firma de contar; el 0 es falta de revisor, no de evidencia.

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
