# C-15 — El predicado ejecutable de «clase completa» (respuesta a Q-AC-5)

**Rama:** `trabajo/c-15-class-predicate` · **Base:** `main` `f8af240` (A-05 integrado) · **Fecha:** 2026-11-05
**Responde a:** Q-AC-5 (A → C) en [`analysis/discussion/threads/a-c.md`](discussion/threads/a-c.md)

A pidió una cosa concreta: el **predicado ejecutable** que usa el contador, con una prueba que lo ejerza, para
que «clase completa» no tenga dos definiciones. Este es.

## Qué había antes

`analysis/class-registry.json` declaraba `count_complete: 0` y una clase rastreada, y
`check-class-registry.py` comprobaba que el número cuadrara con las entradas `complete[]`. Eso detecta una
mentira gruesa, pero no dice **qué hace falta** para que una clase cuente: la regla vivía en prosa, repartida
entre `ROADMAP.md` §5 y las respuestas de la discusión.

Y ya había costado un rojo: `main` `8d21505` fallaba en `check-class-surface-evidence` porque C-03 declaró
evidencia para `<init>` y la etapa seguía esperando «sin evidencia». Lo cazó A al rebasar, no la suite de C,
porque el job `quick` de CI no ejecuta esa etapa.

## Qué hay ahora

### `mc-aot/tools/class-complete-predicate.py`

Lee el registro y, por clase, la evidencia real (manifiesto de classfile + informe), y emite un veredicto
—`complete`, `review-required`, `partial`— con bloqueos nombrados. Reglas:

| Regla | Qué exige | Bloqueo si falla |
|---|---|---|
| R1 | Los miembros del classfile son la autoridad: lo declarado y lo cubierto coinciden, sin inventar ni omitir | `member-without-evidence:<m>` / `member-not-in-classfile:<m>` |
| R2 | Cada miembro tiene evidencia de tipo declarado: `differential` o `java-only` | `unknown-evidence-kind:<m>=<k>` |
| R3 | Un miembro `java-only` solo se excluye si es **inalcanzable sin reflexión** y el informe dice por qué | `reflection-gap:<m>` / `reflection-gap-without-reason:<m>` |
| R4 | `complete` exige revisión de otro frente: `review`, `reviewer` y `certified: true` | `no-review` / `no-reviewer` / `not-certified` |
| R5 | El contador del registro **es** el número de veredictos `complete`; si no coincide, falla | `count_complete` ≠ predicado |

R3 es la condición 1 de A aplicada al pie de la letra: «no lo llama nadie» (inalcanzable) es distinto de «lo
llama algo que no modelamos» (hueco de reflexión). El constructor privado de `QuartPos` entra en el primer
caso, con motivo escrito; si alguien lo marca como alcanzable, la clase pasa a `partial` sin discusión.

### `mc-aot/tests/check-class-complete-predicate.py`

No basta con que el predicado exista: la prueba **intenta engañarlo** ocho veces en un árbol temporal.

1. Subir `count_complete` a mano → el predicado y el registro discrepan y la etapa falla.
2. Marcar el miembro `java-only` como alcanzable → `reflection-gap:<init>()V`.
3. Excluirlo sin motivo escrito → `reflection-gap-without-reason`.
4. Quitarle el diferencial a `fromBlock(I)I` → `member-without-evidence`.
5. Inventar evidencia para `toBlockFromJava(I)I` → `member-not-in-classfile`.
6. Certificar con un bloqueo vivo → `claimed-certified-with-blockers`.
7. Apuntar el manifiesto a otra clase → `class-mismatch`.
8. **El camino honesto:** evidencia + revisión independiente + contador a 1 → el veredicto es `complete`
   y el contador se mueve. Si el predicado no supiera decir «sí», tampoco serviría.

### El informe separa lo que antes se confundía

`analysis/quartpos-evidence-report.json` gana `differential_members`, `java_only_members` y
`unreachable_java_only` (con motivo). El manifiesto gana `members_classification`, y
`class-surface-evidence.py` ahora **verifica esa clasificación** contra la superficie del classfile y la
devuelve, así que un miembro sin clasificar es un error y no un silencio. `check-class-surface-evidence.py`
afirma los tres conjuntos, de modo que la distinción que se perdió en `8d21505` ya no puede perderse sin que
la etapa falle.

## Estado real de `QuartPos` después de esto

```
net/minecraft/core/QuartPos: review-required (status declarado: partial-evidence)
    nota: java-only-unreachable:<init>()V (constructor privado ... solo la reflexión con setAccessible lo alcanza)
    bloqueo: no-review
    bloqueo: no-reviewer
    bloqueo: not-certified
count_complete calculado: 0 · registrado: 0
```

Es decir: la superficie y la evidencia ya alcanzan; lo que falta es que **otro frente la revise**. El contador
sigue en 0 y no lo mueve C solo. Cuando A o B firmen la revisión, el predicado la contará sin que nadie edite
un número.

## Verificación

```sh
export JAVA_HOME=/ruta/al/jdk-25 TMPDIR=/var/tmp
python3 mc-aot/tools/update-quartpos-evidence.py --check
python3 mc-aot/tools/class-surface-evidence.py analysis/class-evidence/quartpos.json
python3 mc-aot/tests/check-class-surface-evidence.py
python3 mc-aot/tools/class-complete-predicate.py
python3 mc-aot/tests/check-class-complete-predicate.py
python3 mc-aot/tools/check-class-registry.py
```

Y en la suite: `check-class-complete-predicate` y `check-class-surface-evidence` son etapas registradas de
`run-regressions.sh`; el job `quick` de CI ejecuta el predicado y su prueba, que es lo que habría cazado el
rojo de `8d21505` antes de llegar a `main`.

## Lo que sigue sin resolverse

- `QuartPos` necesita revisión de A o B; sin ella no cuenta (§ R4). Pedida en Q-AC-5/Q-BC-10.
- El predicado solo conoce un tipo de evidencia más allá del diferencial: `java-only`. Si aparece un caso de
  evidencia estructural (superficie sin ejecución) habrá que decidir si cuenta para algo — hoy **no** cuenta.
- La partición por familias no está conectada al predicado: sigue siendo un mapa de lotes, no un recuento.
