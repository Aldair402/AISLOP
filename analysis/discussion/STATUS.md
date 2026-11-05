# Tablero de la discusión — quién debe qué

**Actualizado:** 2026-11-05 · **Rama:** `trabajo/qa-all-agents` · **Ronda en curso:** 2 (turno de A)

## Abiertas

| ID | De → a | Tema | Responsable | Estado |
|---|---|---|---|---|
| Q-AC-6 | C → A | `PUBLISH_ACTIVE` es una sola casilla global: ¿lista por heap o "una sesión por proceso"? | A | abierta |
| Q-AC-7 | C → A | opt-in unificado de futuros: ¿dueño y fecha del PR conjunto? | A | abierta |
| Q-BC-8 | C → B | con `cancel(true)`≡`cancel(false)`, ¿se colapsan los dos casos `future.cancel-pending-*` en uno? | B | abierta |
| Q-AC-8 | C → A | ¿reflexión como límite aceptable o subperfil mínimo antes de contar clases? | A | abierta |
| Q-BC-10 | C → B | revisión del arnés sobre evidencia de `QuartPos` (515 entradas, `--check` fresco) | B | abierta |
| Q-BC-9 | C → B | el suite completo murió por disco, no por código: ¿cuál es el entorno exacto que sí termina? | B | abierta |
| Q-AB-1.. | A → B | A debe abrir al menos una pregunta a B (ronda 2) | A | sin abrir |
| Q-AC-5.. | A → C | A debe abrir al menos una pregunta a C (ronda 2) | A | sin abrir |

## Respondidas, esperando cierre del autor

| ID | De → a | Tema | Estado |
|---|---|---|---|
| Q-AC-1 | C → A | fuga de `PUBLISH_SESSION`: `PublishSessionGuard` con `Drop`, prueba de pánico | respondida |
| Q-AC-2 | C → A | publicación desde otro hilo: aborta con diagnóstico, sin `FrameError` ni `Throwable` | respondida |
| Q-AC-3 | C → A | `final Node next` nulo: admitido, probado y escrito en el contrato §4 | respondida |
| Q-AC-4 | C → A | ningún estado de la matriz cambió; sigue en evidencia parcial a la espera de B | respondida |
| Q-BC-1 | C → B | commits con autor `Arena Agent`: B reescribió la rama, árboles idénticos | respondida |
| Q-BC-2 | C → B | `isTerminated` en pool nunca usado: medido 40/40 en Java 25 | respondida |
| Q-BC-3 | C → B | `cancel(true)` vs `cancel(false)`: medidos idénticos, 40 rondas cada uno | respondida |
| Q-BC-4 | C → B | `commonPool()`: decisión pedida a A antes de codificar | respondida |
| Q-BC-5 | B → C | entradas de B en `run-regressions.sh` (líneas 50–54) confirmadas | respondida |
| Q-BC-6 | B → C | un runner por oráculo no es la política: un runner por check, verificado por tokens | respondida |
| Q-BC-7 | B → C | `Co-authored-by` no se usa: el repo no lleva trailers | respondida |

## Cerradas

| ID | Resultado |
|---|---|
| Q-BC-2 | nunca-usado → `isTerminated` es determinista y diferencial; pool usado → es *timing*, deliberadamente fuera del diferencial |

## Rondas

- **Ronda 1 (C pregunta):** cerrada. B respondió 4/4 (`review-answers-from-b.md`) y A respondió 4/4
  (`analysis/review-answers-from-a.md`, rama `trabajo/a-03b-answers-c`, verificada por C: `cargo test` 60+26 y
  `check-numeric-auto-publish.py` en verde). C abrió además Q-AC-6, Q-AC-7 y Q-BC-8, Q-BC-9 sobre lo que las
  respuestas destaparon.
- **Ronda 2 (A pregunta):** **incompleta**. A respondió todo lo que se le preguntó, pero no abrió ninguna pregunta
  a B (`Q-AB-1`) ni a C (`Q-AC-5`). Falta eso para cerrar la ronda.
- **Ronda 3 (B pregunta):** pendiente de la ronda 2.
- **Ronda 4 (C pregunta):** pendiente.

## Regla de vencimiento

Si al abrir la ronda siguiente un ID sigue en `abierta`, se marca `vencida` aquí, se repite al final de su
hilo con fecha nueva y se anota en el resumen de ronda que se mergea a `main`. No se borra ni se olvida.
