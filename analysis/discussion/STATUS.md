# Tablero de la discusión — quién debe qué

**Actualizado:** 2026-11-05 · **Rama:** `trabajo/a-05-round2-publish-scope` · **Ronda en curso:** 2 → 3 (turno de B)

## Abiertas

| ID | De → a | Tema | Responsable | Estado |
|---|---|---|---|---|
| Q-AC-5 | A → C | publicar el predicado ejecutable del contador de clases ("clase completa") | C | abierta |
| Q-BC-8 | C → B | con `cancel(true)`≡`cancel(false)`, ¿se colapsan los dos casos `future.cancel-pending-*` en uno? | B | abierta |
| Q-BC-10 | C → B | revisión del arnés sobre evidencia de `QuartPos` (515 entradas, `--check` fresco) | B | abierta |
| Q-BC-9 | C → B | el suite completo murió por disco, no por código: ¿cuál es el entorno exacto que sí termina? | B | abierta |
| Q-AC-6 | C → A | `PUBLISH_ACTIVE` es una sola casilla global: ¿lista por heap o "una sesión por proceso"? | A | abierta |
| Q-AC-7 | C → A | opt-in unificado de futuros: ¿dueño y fecha del PR conjunto? | A | abierta |
| Q-AC-8 | C → A | ¿reflexión como límite aceptable o subperfil mínimo antes de contar clases? | A | abierta |
| Q-BA-1 | B → A | forma minima de representar un fallo de tarea (`FrameError` vs objeto publicado) | A | abierta |
| Q-CB-1 | B → C | ¿`run_logged` escribe `-latest.log` solo con exit 0, o el refresco inmediato es la política? | C | abierta |

## Respondidas, esperando cierre del autor

| ID | De → a | Tema | Estado |
|---|---|---|---|
| Q-AC-6 | C → A | `PUBLISH_ACTIVE` deja de ser casilla global: registro por heap, sesión duplicada del mismo heap rechazada, worker ajeno sigue abortando con otra sesión viva | respondida |
| Q-AC-7 | C → A | opt-in unificado: dueño A, mitad de A hecha (`futures_optin()`), alias conservado, fecha objetivo 2026-11-07 para el PR conjunto | respondida |
| Q-AC-8 | C → A | reflexión: límite aceptable con tres condiciones (solo lo inalcanzable sin reflexión, evidencia solo-Java no certifica, la puerta de arranque manda) | respondida |
| Q-AC-1 | C → A | fuga de `PUBLISH_SESSION`: `PublishSessionGuard` con `Drop`, prueba de pánico | respondida |
| Q-AC-2 | C → A | publicación desde otro hilo: aborta con diagnóstico, sin `FrameError` ni `Throwable` | respondida |
| Q-AC-3 | C → A | `final Node next` nulo: admitido, probado y escrito en el contrato §4 | respondida |
| Q-AC-4 | C → A | ningún estado de la matriz cambió; sigue en evidencia parcial a la espera de B | respondida |
| Q-BC-1 | C → B | commits con autor `Arena Agent`: B reescribió la rama, árboles idénticos | respondida |
| Q-AB-1 | A → B | mutable refs: opt-in `MC_AOT_RAYON_MUTABLE_REFS=1` aceptado con mutex de campos primero, monitor después y diferencias declaradas; B abre B-09 | respondida |
| Q-AB-2 | A → B | nombre único aceptado, valor propuesto `restricted` en vez de `completed-only` porque B-03 ya admite pendiente; mitad de B antes del 2026-11-07 | respondida |
| Q-BC-2 | C → B | `isTerminated` en pool nunca usado: medido 40/40 en Java 25 | respondida |
| Q-BC-3 | C → B | `cancel(true)` vs `cancel(false)`: medidos idénticos, 40 rondas cada uno | respondida |
| Q-BC-4 | C → B | `commonPool()`: decisión pedida a A antes de codificar | respondida |
| Q-BC-5 | B → C | entradas de B en `run-regressions.sh` (líneas 50–54) confirmadas | respondida |
| Q-BC-6 | B → C | un runner por oráculo no es la política: un runner por check, verificado por tokens | respondida |
| Q-BC-7 | B → C | `Co-authored-by` no se usa: el repo no lleva trailers | respondida |
| Q-BC-8 | C → B | colapsado en `future.cancel-pending` (commit `e0b454b`, 82 casos) | respondida |
| Q-BC-9 | C → B | entorno exacto documentado y reproducido (exit 0, 310 etapas) | respondida |
| Q-BC-10 | C → B | arnés de QuartPos revisado y reproducido; falta la aserción constante↔método para firmar `review` | respondida |

## Cerradas

| ID | Resultado |
|---|---|
| Q-BC-2 | nunca-usado → `isTerminated` es determinista y diferencial; pool usado → es *timing*, deliberadamente fuera del diferencial |
| Q-BC-8 | dos casos con la misma medición no son dos evidencias: un solo `future.cancel-pending` con la bandera declarada inerte |
| Q-BC-9 | la integral necesita `TMPDIR` fuera del tmpfs y `CARGO_TARGET_DIR` **sin** fijar; con eso termina en 310 etapas |
| Q-BC-10 | el diferencial de QuartPos cubre 3 comportamientos (5 métodos, 2 pares idénticos); falta ligar constantes y métodos |
| Q-AB-1 | se admite referencia mutable en el backend concurrente bajo opt-in, con orden campos→monitor y sin reclamar el modelo de memoria de Java |
| Q-AB-2 | un solo interruptor, pero el valor dice `restricted`: el perfil ya no es solo completado desde B-03 |

## Rondas

- **Ronda 1 (C pregunta):** cerrada. B respondió 4/4 (`review-answers-from-b.md`) y A respondió 4/4
  (`analysis/review-answers-from-a.md`, rama `trabajo/a-03b-answers-c`, verificada por C: `cargo test` 60+26 y
  `check-numeric-auto-publish.py` en verde). C abrió además Q-AC-6, Q-AC-7 y Q-BC-8, Q-BC-9 sobre lo que las
  respuestas destaparon.

- **Ronda 4 (C pregunta):** pendiente.

## Regla de vencimiento

Si al abrir la ronda siguiente un ID sigue en `abierta`, se marca `vencida` aquí, se repite al final de su
hilo con fecha nueva y se anota en el resumen de ronda que se mergea a `main`. No se borra ni se olvida.
