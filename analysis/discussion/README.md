# Discusión A ↔ B ↔ C — una sola rama, todos preguntan y todos responden

**Rama:** `trabajo/qa-all-agents` · **Base:** `main` (15ee6dd) · **Idioma:** español en los hilos, inglés en los commits

Esta rama es el **único** lugar donde A, B y C se cuestionan mutuamente. No es "C revisa a A y B":
cada agente abre preguntas a los otros dos y responde las que recibe. El objetivo del proyecto lo exige —
prompts distintos dan seeds distintas, y ninguna respuesta se acepta sin evidencia reproducible.

## Quién participa

| Agente | Rama de trabajo | Frente |
|---|---|---|
| A | `trabajo/a-01-contrato-heap` | heap, publicación numérica, `FrameError`, `availableProcessors` |
| B | `trabajo/b-01-contrato-futures` | contrato de futuros, pool Rayon, oráculos `CompletableFuture`/`ForkJoinPool` |
| C | `trabajo/c-01-baseline` y tareas `c-XX-*` | registro de clases, partición, suite, CI |

## Dónde se escribe

Un archivo por pareja, en `analysis/discussion/threads/`:

- `a-b.md` — A ↔ B
- `a-c.md` — A ↔ C
- `b-c.md` — B ↔ C

Cada archivo tiene **una sección por dirección** (`De A a B`, `De B a A`). Así dos agentes pueden
escribir a la vez en el mismo hilo sin pisarse.

`analysis/discussion/STATUS.md` es el tablero: qué está abierto, quién lo debe, qué ronda toca.

Las **actas originales** se conservan sin tocar como fuente histórica:
`analysis/review-questions-for-a-and-b.md` (preguntas de C) y `analysis/review-answers-from-b.md` (respuestas de B).
Los hilos las citan; no las reescriben.

## Formato de una entrada

```md
### Q-BC-4 · de B a C · 2026-11-05 · estado: abierta

**Contexto:** una o dos frases de por qué importa.
**Pregunta:** una sola pregunta decidible, no un tema.
**Evidencia:** rutas, commits o líneas de log que la sostienen.

**Respuesta (C):** _pendiente_
```

- ID `Q-XY-n`: X = quien pregunta, Y = quien responde, n = consecutivo dentro del hilo.
- La respuesta se escribe debajo, con el mismo ID y prefijo `A-XY-n`, y se actualiza `estado:` a
  `respondida` o `cerrada`. `cerrada` = hay evidencia o hay decisión, no queda duda.

## Reglas

1. **Solo se agrega.** Nunca se reescribe la pregunta ni la respuesta de otro. Si algo cambió, se
   responde de nuevo citando el ID anterior.
2. **Evidencia o no cuenta.** Cada respuesta cita commit, ruta y línea de log, o número de ronda medido.
   "Ya lo probé" no es respuesta.
3. **Una pregunta = una decisión.** Si aparecen dos temas, son dos IDs.
4. **El código no se toca en esta rama.** Si una respuesta exige cambiar código, se hace en la rama de
   tarea del responsable; acá solo se enlaza el commit.
5. **`main` nunca se rompe y `count_complete` sigue en 0.** Ninguna respuesta puede proponer contar una
   clase como completa sin pasar los criterios del ROADMAP.
6. **Respuesta vencida se escala, no se ignora.** Si el turno pasó y hay preguntas abiertas, se marca
   `vencida` en `STATUS.md` y se repite el ID al final del hilo con la fecha nueva.
7. **Cada ronda, cada agente abre al menos una pregunta a cada uno de los otros dos.** Es la diferencia
   entre un foro y una revisión de una sola vía.

## Rotación

| Ronda | Quien pregunta | Quien responde | Estado |
|---|---|---|---|
| 1 | C → A y B | A, B | preguntas abiertas; B ya respondió las suyas |
| 2 | A → B y C, y responde a C | B, C | **en curso: turno de A** |
| 3 | B → A y C, y responde a A | A, C | pendiente |
| 4 | C → A y B, y responde a A y B | A, B | pendiente |

Al cerrar cada ronda, C destila el resultado en un solo `analysis/discussion/round-NN-resumen.md` y eso
es lo único que se mergea a `main`; la discusión vive en esta rama.

## Cómo se publica

```bash
git fetch origin trabajo/qa-all-agents
git switch trabajo/qa-all-agents          # o rebase sobre ella
# editar SOLO tu sección del hilo correspondiente
git add analysis/discussion
git commit -m "Ask A about publish session leak"     # imperativo, inglés, una línea
git push origin trabajo/qa-all-agents
```

Autor y committer: `MIlaSoraki <mila.gastelum@autistici.org>`. Si al hacer push hay conflicto, se
conservan **ambas** entradas y se renumera la más nueva: nunca se descarta la de otro.

## Evidencia que ya existe y conviene citar en vez de repetir

- Suite completa: `analysis/full-regressions-a03.log` (309 líneas, 306 etapas, exit 0).
- Contrato de futuros: `mc-aot/tests/check-futures-contract.py` → `differential=23, guard=19, huecos=7`.
- Cancelación y futuro pendiente: `mc-aot/tests/check-rayon-pending-future.py`, 48 resultados.
- Publicación automática numérica: `mc-aot/tests/check-numeric-auto-publish.py`, 20 rondas Java/Rust.
- Registro y partición: `mc-aot/tools/check-class-registry.py` (1 clase rastreada, `count_complete=0`),
  `check-family-partition.py` (6 lotes, 5801/7762 clases cubiertas).
- CI: `.github/workflows/ci.yml` + `analysis/c10-ci-jar-fetch.md` (quick + focused en verde).
