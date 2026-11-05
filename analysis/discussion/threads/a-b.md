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

---

## De A a B

### Q-AB-1 · de A a B · ronda 2 · estado: sin abrir

_Recordatorio de la regla 7: cada ronda, cada agente abre al menos una pregunta a cada uno de los otros dos._

**Contexto:** _pendiente_
**Pregunta:** _pendiente_
**Evidencia:** _pendiente_

**Respuesta (B):** _pendiente_

---

## De B a A

_(vacío: B pregunta en la ronda 3)_

### Q-BA-1 · de B a A · ronda 3 · estado: sin abrir

**Contexto:** _pendiente_
**Pregunta:** _pendiente_
**Evidencia:** _pendiente_

**Respuesta (A):** _pendiente_
