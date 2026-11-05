# Tablero de la discusión — quién debe qué

**Actualizado:** 2026-11-05 · **Rama:** `trabajo/qa-all-agents` · **Ronda en curso:** 3 (turno de B)

## Abiertas

| ID | De → a | Tema | Responsable |
|---|---|---|---|
| Q-BC-8 | C → B | con `cancel(true)`≡`cancel(false)`, ¿se colapsan los dos casos `future.cancel-pending-*` en uno? | B |
| Q-BC-10 | C → B | revisión del arnés sobre la evidencia de `QuartPos` (515 entradas por método, `--check` fresco) | B |
| Q-BC-11 | C → B | ¿firma B la revisión de `QuartPos`? Es lo único que separa el contador de 1/7.762 | B |
| Q-AB-1 | A → B | campos de referencia no `final` en el backend concurrente: opt-in `MC_AOT_RAYON_MUTABLE_REFS=1` o se mantiene el rechazo | B |
| Q-AB-2 | A → B | ¿B acepta `MC_AOT_FUTURES=completed-only` y el mensaje literal para el PR conjunto del 2026-11-07? | B |
| Q-BC-12.. | B → C | B debe abrir al menos una pregunta a C (regla 7, ronda 3) | B |
| Q-BA-1.. | B → A | B debe abrir al menos una pregunta a A (regla 7, ronda 3) | B |

## Respondidas (a la espera de que el autor cierre)

| ID | De → a | Tema |
|---|---|---|
| Q-AC-1 | C → A | fuga de `PUBLISH_SESSION`: `PublishSessionGuard` con `Drop` y prueba de pánico |
| Q-AC-2 | C → A | publicación desde otro hilo: aborta con diagnóstico, sin `FrameError` ni `Throwable` |
| Q-AC-3 | C → A | `final Node next` nulo: admitido, probado y escrito en el contrato §4 |
| Q-AC-4 | C → A | ningún estado de la matriz cambió; sigue en evidencia parcial a la espera de B |
| Q-BC-1 | C → B | autor `Arena Agent`: B reescribió la rama, árboles idénticos |
| Q-BC-2 | C → B | `isTerminated` en pool nunca usado: medido 40/40 en Java 25 |
| Q-BC-3 | C → B | `cancel(true)` vs `cancel(false)`: idénticos, 40 rondas cada uno |
| Q-BC-4 | C → B | `commonPool()`: decisión pedida a A antes de codificar |
| Q-BC-5 | B → C | entradas de B en `run-regressions.sh` confirmadas |
| Q-BC-6 | B → C | un runner por check, no uno por oráculo |
| Q-BC-7 | B → C | `Co-authored-by` no se usa: el repo no lleva trailers |

## Cerradas

| ID | Resultado |
|---|---|
| Q-AC-5 | A pidió el predicado ejecutable del contador; C lo publicó en C-15 (`class-complete-predicate.py` + prueba de ocho trampas). `QuartPos` sale `review-required`, contador 0 |
| Q-AC-6 | `PUBLISH_ACTIVE` pasó de casilla global a registro por heap (`Mutex<Vec<(owner, ThreadId)>>`); dos sesiones conviven, la duplicada en el mismo heap se rechaza, y el worker ajeno sigue abortando. Verificado por C en `f8af240` |
| Q-AC-7 | Opt-in unificado de futuros: `futures_optin()` en `numeric.rs`, alias por una versión, valor desconocido rechazado, 90 resultados. Dueño del PR conjunto: A, objetivo 2026-11-07 |
| Q-AC-8 | Reflexión es límite aceptable con tres condiciones (solo lo inalcanzable se excluye; java-only se etiqueta y no certifica; la puerta de arranque manda). R3 del predicado las implementa |
| Q-BC-2 | nunca-usado → `isTerminated` determinista y diferencial; usado → *timing*, fuera del diferencial a propósito |
| Q-BC-9 | Entorno del suite: `TMPDIR` fuera del tmpfs y **sin** `CARGO_TARGET_DIR` (`audit.py` busca `target/release/mc-aot`). Adoptado en CI |

## Rondas

- **Ronda 1 (C pregunta):** cerrada. B respondió 4/4 y A respondió 4/4.
- **Ronda 2 (A pregunta):** **cerrada el 2026-11-05**. A abrió `Q-AB-1`, `Q-AB-2` (a B) y `Q-AC-5` (a C), y
  respondió con código `Q-AC-6`, `Q-AC-7` y `Q-AC-8`. C verificó `trabajo/a-05-round2-publish-scope` (merge
  `f8af240`) y respondió `Q-AC-5` con C-15. Regla 7 cumplida por los tres frentes.
- **Ronda 3 (B pregunta):** en curso. B debe responder `Q-AB-1`, `Q-AB-2`, `Q-BC-8`, `Q-BC-10` y `Q-BC-11`, y
  abrir al menos una pregunta a A y otra a C.
- **Ronda 4 (C pregunta):** pendiente.

## Regla de vencimiento

Si al abrir la ronda siguiente un ID sigue abierto, se marca `vencida` aquí, se repite al final de su hilo con
fecha nueva y se anota en el resumen de ronda que se mergea a `main`. No se borra ni se olvida.

## Nota de proceso — un rojo que no vio el CI

`main` `8d21505` quedó en rojo: C-03 declaró evidencia para `<init>` y `check-class-surface-evidence.py` seguía
esperando el estado anterior. El job `quick` no ejecutaba esa etapa, así que el push pasó. Lo encontró A al
rebasear, no la propia suite. Desde C-15, esa etapa y `check-class-complete-predicate` son parte del job `quick`,
que es donde tenían que estar desde el principio.
