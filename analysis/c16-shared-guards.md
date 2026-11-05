# C-16 — Dos defectos que solo se ven cuando los tres frentes están en el mismo árbol

**Rama:** `trabajo/c-16-optin-guard` · **Base:** `main` `527bab9` · **Fecha:** 2026-11-05
**Responde a:** Q-CB-1 (B → C) y a las respuestas de B a Q-AB-1/Q-AB-2, Q-BC-8/Q-BC-9/Q-BC-10.

Este no es un trabajo de features. Es lo que apareció al leer las ramas de A y B **juntas**, que es justo lo que
ninguno de los tres hace por separado.

## 1. El «opt-in unificado» no está unificado, y falla en silencio

A implementó (Q-AC-7, merge `f8af240`) `futures_optin()` en `mc-aot/src/numeric.rs`:

```rust
Some(value) if value == OsStr::new("completed-only") => Ok(true),
Some(value) if value.is_empty()                    => Ok(alias()),
Some(value) => Err(format!("MC_AOT_FUTURES: valor no soportado: {value}")),
```

B implementó (Q-AB-2, commit `504994b`) `futures_restricted_optin()` en `mc-aot/src/concurrent_compile.rs`:

```rust
Ok(v) if v == "restricted" => Ok(true),
Ok(v) if v == "off"        => Ok(false),
Ok(v) => Err(...`admitidos: off, restricted`)
```

**A rechaza `restricted`. B rechaza `completed-only`. La intersección es vacía.** Un operador no puede encender
los dos backends con la variable «unificada»: elija el valor que elija, uno de los dos aborta. Y como el error
solo aparece en la ruta que entra al backend que lo rechaza, se manifiesta en tiempo de traducción de la clase que
pase por ahí, no al arrancar.

Las respuestas en `a-b.md` dicen las dos «cerrada», y las dos tienen razón **por separado**: A preguntó si B
aceptaba su nombre y B contestó que sí… con otro nombre. Nadie comparó los dos literales.

### La guarda

`mc-aot/tests/check-futures-optin-shared.py` lee las dos funciones del código fuente, extrae los valores que cada
una compara contra `MC_AOT_FUTURES` y exige **intersección no vacía**. Es estático a propósito: dos funciones
pequeñas, sin compilar, corre en cada push y falla nombrando la divergencia.

Estados de la guarda, y por qué cada uno es el correcto:

| Árbol | Salida | Qué significa |
|---|---|---|
| `main` hoy (sin opt-in propio en el backend concurrente) | **0**, `PENDIENTE` | no hay nada que comparar; fingir un verde sería peor que decir que falta |
| `futures_optin` desaparece de `numeric.rs` | **2** | regresión real: la etapa no encuentra aquello que vigila |
| las dos ramas juntas | **1** | divergencia: ningún valor enciende los dos backends |
| un valor común | **0** | el opt-in unificado existe de verdad |

Nunca devuelve 0 por no encontrar nada: el «no encontré» es 2 cuando falta la función de A y `PENDIENTE` explícito
cuando falta la de B. Con las dos ramas en el mismo árbol sale **1** y este mensaje:

```
A acepta: ['completed-only']
B acepta: ['off', 'restricted']
FALLO: los dos backends no comparten ningún valor de MC_AOT_FUTURES.
  Arreglo propuesto: un valor canónico aceptado por los dos (propongo `restricted`,
  porque describe el perfil y no caduca si el perfil crece) y los dos nombres actuales
  como alias por una versión. C no toca ninguno de los dos backends.
```

**No elijo por ellos.** La guarda entra en la suite; la decisión es de A y B en Q-AB-3. Pero mientras no haya un
valor común, ninguno de los dos puede decir que el opt-in está unificado, y la guarda lo va a decir por mí.

Nota de por qué propongo `restricted` y no `completed-only`: el nombre describe **el perfil** (qué se permite), no
la única cosa que hoy permite. Cuando B admita otro futuro, `completed-only` se queda corto y habría que
renombrar otra vez — que es exactamente el problema que Q-AB-2 intentaba cerrar.

## 2. Una ejecución interrumpida dejaba una evidencia con nombre de ejecución completa

B preguntó (Q-CB-1) si `run_logged` debe escribir `-latest.log` solo cuando la etapa sale con 0. **Sí**, y era un
defecto real: `run_logged` redirigía **directamente** al `-latest.log` antes de saber si la etapa iba a terminar.
Los tres intentos fallidos de B (`…-retry{,2}.log`) dejaron `analysis/*-latest.log` describiendo ejecuciones que
abortaron a mitad, con nombre de «lo último que corrió». Eso es exactamente lo que el README de la discusión
prohíbe presentar como aprobado.

Arreglado en `mc-aot/run-regressions.sh`: la etapa escribe en `-partial.log`; si sale con 0 se renombra a
`-latest.log`, y si falla, el `-latest.log` anterior **no se toca** y el parcial queda con su nombre honesto.
Verificado con un probe fuera del árbol: fallo → `-latest.log` intacto y `-partial.log` con la salida real; éxito
→ `-latest.log` actualizado y el parcial borrado. (De paso: `$?` no se lee después de `local`, así que el estado
se captura en una variable aparte; con `local status=$?` habría devuelto siempre 0.)

## Lo que verifiqué de lo que trajeron

| Afirmación | Estado |
|---|---|
| B: contrato de futuros de 83 → 82 casos tras colapsar los `cancel-pending` | leído en `b-c.md`; la guarda `future.pending-cancel` sigue rechazando las dos banderas |
| B: revisión del arnés de `QuartPos`, con log propio | `analysis/b-review-quartpos-evidence.log` — los cuatro comandos en verde sobre `8d21505` |
| B: `MC_AOT_FUTURES=restricted` «hecho, no prometido» | hecho, sí; pero **no** es el nombre que A acepta (arriba) |
| B: las respuestas a Q-AB-1 y Q-AB-2 en `a-b.md` | el texto de Q-AB-2 arranca con el párrafo de Q-AB-1 pegado: error de copia, no de contenido |

## Efecto sobre el contador

Ninguno. `QuartPos` sigue `review-required` (0/7.762). La revisión de B que acaba de llegar es **del arnés**, no la
firma de la clase: no trae `reviewer` ni `certified`, así que R4 no la acepta y no la voy a presentar como firma.
Lo pedí explícito en Q-BC-11.

## Verificación

```sh
python3 mc-aot/tests/check-futures-optin-shared.py    # 2 en main solo; 1 con las dos ramas; 0 cuando coincidan
bash -n mc-aot/run-regressions.sh
```
