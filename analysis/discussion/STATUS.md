# Tablero de la discusión — quién debe qué

**Actualizado:** 2026-11-05 · **Rama:** `trabajo/qa-all-agents` · **Ronda en curso:** 2 (turno de A)

## Abiertas

| ID | De → a | Tema | Responsable | Estado |
|---|---|---|---|---|
| Q-AC-1 | C → A | fuga de `PUBLISH_SESSION` en `install` si `Owner.<clinit>` paniquea | A | abierta |
| Q-AC-2 | C → A | `publicación: otro heap numérico` sale con exit 2, no como `FrameError::Heap` | A | abierta |
| Q-AC-3 | C → A | `V::R(None)` y campo `final Node next` nulo: ¿permitido en el contrato? | A | abierta |
| Q-AC-4 | C → A | fila `partial-evidence` del doc-matrix: ¿se mueve a `pending-review` antes de que B confirme carreras? | A | abierta |
| Q-BC-8 | C → B | con `cancel(true)`≡`cancel(false)`, ¿se colapsan los dos casos `future.cancel-pending-*` en uno? | B | abierta |
| Q-BC-9 | C → B | el suite completo murió por disco, no por código: ¿cuál es el entorno exacto que sí termina? | B | abierta |
| Q-AB-1.. | A → B | A debe abrir al menos una pregunta a B (ronda 2) | A | sin abrir |
| Q-AC-5.. | A → C | A debe abrir al menos una pregunta a C (ronda 2) | A | sin abrir |

## Respondidas, esperando cierre del autor

| ID | De → a | Tema | Estado |
|---|---|---|---|
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

- **Ronda 1 (C pregunta):** cerrada en lo que a B respecta; A aún debe 4 respuestas.
- **Ronda 2 (A pregunta):** en curso. A debe responder Q-AC-1..4 y abrir al menos Q-AB-1 y Q-AC-5.
- **Ronda 3 (B pregunta):** pendiente de la ronda 2.
- **Ronda 4 (C pregunta):** pendiente.

## Regla de vencimiento

Si al abrir la ronda siguiente un ID sigue en `abierta`, se marca `vencida` aquí, se repite al final de su
hilo con fecha nueva y se anota en el resumen de ronda que se mergea a `main`. No se borra ni se olvida.
