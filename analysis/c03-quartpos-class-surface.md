# C-03 — QuartPos como candidato a primera clase completa

**Rama:** `trabajo/c-14-quartpos-surface` · **Base:** `main` `eead7b5` · **Fecha:** 2026-11-05
**Clase:** `net/minecraft/core/QuartPos` · **SHA-256 del classfile:** `0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c`
**Resultado:** superficie cerrada y constructor medido; **la clase sigue parcial y el contador sigue en 0**.

## Qué faltaba antes de esta rama

El inventario anterior decía «5/6 métodos y 4/4 campos» y dejaba `<init>()V` como hueco. Peor: la
reconciliación de la superficie con el classfile era **manual** — alguien la escribió en un JSON y nadie la
volvía a comprobar contra los bytes. Eso es precisamente el tipo de número que se desactualiza sin que nadie
lo note.

## Qué se hizo

1. **`mc-aot/tools/classfile-surface.py`** — parser de classfile en Python puro, sin JDK: lee el pool de
   constantes, `access_flags`, superclase, interfaces, y todos los campos y métodos con sus flags, incluidos
   privados, sintéticos y bridge, más la presencia de `<init>` y `<clinit>`. Con `--registry` falla si el
   JSON del registro no coincide con el bytecode; con `--manifest` escribe un manifiesto determinista.

   Superficie real de QuartPos leída de los bytes:

   | Elemento | Detalle |
   |---|---|
   | flags de clase | `public final super` (`0x0031`) |
   | superclase | `java/lang/Object`, sin interfaces |
   | `<clinit>` | **no existe** |
   | campos (4) | `BITS:I=2`, `SIZE:I=4`, `MASK:I=3` públicos; `SECTION_TO_QUARTS_BITS:I=2` privado |
   | métodos (6) | `fromBlock`, `quartLocal`, `toBlock`, `fromSection`, `toSection` (`public static`) y `<init>()V` (`private`) |

2. **`check-quartpos-class-surface.py` ampliado** — ahora hace tres cosas:
   - contrasta la superficie del parser con **reflexión de Java 25** del mismo JAR: flags de clase,
     superclase, número de interfaces, campos declarados, métodos declarados y modificadores por miembro.
     Dos lecturas independientes del mismo bytecode.
   - ejecuta el **constructor privado** por reflexión: sin `setAccessible` debe lanzar
     `IllegalAccessException`; con `setAccessible` debe construir una instancia de `net/minecraft/core/QuartPos`.
   - mantiene el diferencial de los cinco métodos estáticos y las cuatro constantes (515 entradas por método,
     incluidos `Integer.MIN_VALUE`/`MAX_VALUE`, vecindad y 500 valores aleatorios con semilla fija).

3. **`mc-aot/tools/update-quartpos-evidence.py`** — regenera log, manifiesto de miembros, manifiesto de
   classfile e informe **con los hashes calculados en la ejecución**. Con `--check` falla si la evidencia
   commiteada no coincide con una ejecución fresca, que es la forma de detectar evidencia podrida.

4. **Suite y CI** — `run-regressions.sh` gana tres entradas (`check-classfile-surface`,
   `check-quartpos-evidence-audit`, `check-quartpos-evidence-fresh`) y el job `quick` de CI ejecuta las mismas
   tres antes del registro y la partición.

## Por qué la clase no se cuenta todavía

Criterio 2 del ROADMAP pide traducción implementada y evidencia diferencial de la superficie. Los cinco
métodos estáticos y las cuatro constantes lo cumplen. El constructor **no**: en Java su conducta observable es
`IllegalAccessException` (o una instancia, si se fuerza con `setAccessible`), y el traductor no implementa
reflexión. Ese comportamiento no tiene contraste nativo posible hoy, así que se registra como **solo-Java** y
se declara como límite explícito. Contarlo como completo mezclaría «no hay diferencia porque no hay camino»
con «medí que son iguales», y esas dos cosas no valen lo mismo.

El contador sigue en **0**, `status` sigue en `partial-evidence` y la clase **no** entra en `complete[]`.

## Evidencia reproducible

```sh
export JAVA_HOME=/ruta/al/jdk-25 TMPDIR=/var/tmp
python3 mc-aot/tools/classfile-surface.py net.minecraft.core.QuartPos --registry analysis/class-registry.json
python3 mc-aot/tools/class-surface-evidence.py analysis/class-evidence/quartpos.json
python3 mc-aot/tools/update-quartpos-evidence.py --check
python3 mc-aot/tests/check-quartpos-class-surface.py
python3 mc-aot/tools/check-class-registry.py
```

Salidas verificadas en esta rama (2026-11-05):

- `OK: registry matches classfile — 6 methods (6 with evidence), 4 fields, <init>=True <clinit>=False`
- `OK: 2579 resultados diferenciales … superficie reconciliada classfile↔reflexión … constructor privado medido como solo-Java …`
- `OK: la evidencia commiteada coincide con una ejecución fresca`
- `OK: registry valid — 1 tracked, count_complete=0 …`

## Lo que sigue faltando para el primer hito (1 clase completa)

1. Que A o B **revisen** esta evidencia (`review` no nulo en el registro). Sin revisión de otro frente la
   clase no pasa a `pending-review`, mucho menos a `complete`.
2. Una decisión de proyecto sobre reflexión: o se implementa lo suficiente para reproducir estos dos casos
   (acceso denegado y forzado), o el criterio de clase completa admite por escrito que un constructor privado
   inalcanzable salvo por reflexión se cubre con evidencia solo-Java. Hoy **no** está admitido, y no se va a
   dar por admitido sin que lo diga otro frente.
3. Repetir la medición sobre un clon limpio y registrar el hash de la herramienta y del log junto al commit.
