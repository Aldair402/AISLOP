# A-02 fase 2 — el perfil de layouts medido contra el JAR oficial

Fecha: 2026-11-06. Entrada anterior que este documento corrige: `analysis/a02-layout-validation.md`
decía «0 de 687 candidatas, **0** aceptadas por el perfil». Ese número estaba **desactualizado** y,
peor, no era medible: el log `analysis/a02-vanilla-scan.log` tiene una sola línea y no guardó de
dónde salieron las 687 ni qué cláusula falló en cada una.

## 1. Lo que hay hoy, medido

`mc-aot/tests/check-vanilla-layout-profile.py` (registrada en `run-regressions.sh:48`) hace tres
cosas y ninguna es decorativa:

1. **Censo de las 7.762 clases** del JAR oficial con el parser puro-Python de
   `classfile-surface.py` aplicando *literalmente* las cláusulas de `numeric_bridge_layout.verify`,
   y cerrando el grafo de referencias como lo cierra el verificador.
2. **Verificación real** de cada clase admitida por la ruta de verdad (`mc-aot inspect`), exigiendo
   que el SHA-256 del classfile coincida con el que el layout declara.
3. **Contraste de parsers**: Rust (`mc-aot inspect`) y Python, escritos por separado, deben coincidir
   campo a campo —flags incluidos— en clases reales de Minecraft. Hoy: 12 clases, 0 diferencias.

Resultado actual:

| Medida | Valor |
|---|---|
| Clases en el JAR oficial | 7.762 |
| Aceptadas por el perfil con grafo cerrado | **165** |
| De ellas, con campos de instancia | **1** (`SleepStatus`: dos `int`) |
| Controles negativos sobre bytes reales (quitar `final`, marcar abstracta, truncar, hash ajeno, clase ausente) | 5 rechazos correctos |
| Clases comparadas entre los dos parsers | 12, sin diferencias |

Hasta el 2026-11-06 eran 6 y **ninguna tenía campos**: clases de utilidades con métodos estáticos y
constructor privado, layouts reales pero vacíos. Con el tipo cerrado por ausencia de subclases
(véase §3) son **165**, y una tiene estado de verdad:

| Clase vanilla | Campos de instancia | Por qué es cerrada |
|---|---|---|
| `net/minecraft/server/players/SleepStatus` | `int activePlayers`, `int sleepingPlayers` | no es `final`, pero **nada en el JAR la extiende** |

Ese es el primer layout de un objeto de Minecraft sacado de sus bytes: dos ranuras, en el orden del
classfile, con el hash del classfile y la comprobación de que la clase no tiene subclases. Sigue sin
ser una clase traducida ni ejecutable; es su contrato de campos.

## 2. Por qué el resto no entra (censo)

Primer bloqueo por clase, sobre las 7.762 (`--simulate` para el detalle):

| Cláusula que la bloquea primero | Clases |
|---|---|
| `superclase` (no extiende `java/lang/Object`) | 3.525 |
| `clase-abstracta/interfaz/enum` | 1.291 |
| `interfaces` | 933 |
| `clinit` | 622 |
| tipo no cerrado (no `final` **y** con subclases en el JAR) | 485 |
| `nombre-fuera-del-perfil` | 343 |
| `ref-fuera-del-perfil` | 148 |
| `estaticos` | 115 |
| `ref-no-final` | 68 |
| `int-final` | 23 |
| `descriptor` | 21 |

Antes de cerrar por ausencia de subclases, la cláusula «no es `final` a secas» bloqueaba 5.377
clases y los estáticos solo 12; la explicación escrita («casi todas tienen estáticos») era falsa en
ambos sentidos. El muro real es la **superclase**: 3.525 clases extienden algo que no es `Object`.

La razón de fondo es de diseño: el perfil exige que la clase sea cerrada (nada la extiende) y que su
padre sea `java/lang/Object`. En Minecraft casi ningún objeto cumple eso.

## 3. Tipo cerrado sin exigir `final` (implementado el 2026-11-06)

El perfil exigía `final`. Eso no es lo que protege el layout: lo que lo protege es que **no exista
una subclase**, porque una instancia de la subclase no cabe en el layout del padre. En un traductor
AOT de mundo cerrado eso se comprueba leyendo el JAR: si ninguna clase lo extiende, el tipo está
cerrado aunque no lleve la bandera `ACC_FINAL`.

`numeric_bridge_layout.verify` construye ahora la tabla de clases extendidas leyendo el `super_class`
real de cada classfile (parser puro-Python del suite, cacheada por identidad del fichero) y:

- rechaza la clase si no es `final` **y** alguna clase del JAR la extiende, con el mensaje
  «clase debe ser final o estar cerrada (tiene subclases en el JAR)»;
- deja constancia en el layout de **por qué** se consideró cerrada: `closed_by: "final"` o
  `closed_by: "no-subclasses"`, para que nadie lea «final» donde no lo hay;
- la condición de mundo cerrado va escrita en `limitations`: si aparece una subclase nueva, el
  layout deja de valer.

Coste: 6 → **165** clases aceptadas y la primera con campos. Riesgo: aceptar una clase que en
tiempo de ejecución reciba una subclase generada; en este proyecto no existe esa vía (no hay
`ClassLoader`, ni proxy dinámico, ni carga en caliente), y por eso el mundo cerrado es legítimo aquí
y no lo sería en un runtime Java general.

## 4. La separación que faltaba: layout ≠ ejecución

El verificador rechaza por cosas que **no describen el layout de un objeto**:

- `estaticos` y `clinit` son capacidad de **ejecución** (A-05). Un campo estático no ocupa el objeto.
- `interfaces` afectan al **despacho**, no a los campos.
- el **cierre de referencias** es una exigencia del arnés (el grafo debe estar completo), no del
  layout: el destino se puede describir cuando haga falta.

Al separarlas, el número deja de ser «0 y no hay camino» y pasa a ser una tabla de qué compra cada
relajación. Medido con `layout-profile-census.py --plan` (fijado en la prueba para que no derive),
**con el tipo cerrado ya implementado**:

| Paso | Clases | Con campos | Campos de instancia |
|---|---|---|---|
| Perfil actual de `numeric_bridge_layout.verify` | **165** | **1** | **2** |
| + estáticos y `clinit` fuera del criterio de layout | 291 | 1 | 2 |
| + interfaces fuera del criterio de layout | 470 | 5 | 10 |
| + refs de instancia sin cierre (layout del destino bajo demanda) | **651** | **186** | **375** |

Lectura honesta de la tabla:

- Las dos primeras filas no cambian nada material: sin tocar `final` y la supercadena no hay objetos.
- El salto grande es el último: **186 clases con 375 campos de instancia** se pueden describir sin
  ninguna capacidad de ejecución nueva. Es el techo realista de A-02 fase 2 hoy.
- Quedan **309 clases con campos bloqueadas solo por `descriptor`**: `J`, `F`, `D`, `Z`, `B`, `C`, `S`.
  El puente numérico solo tiene ranura `Int` y referencias. Sin ranuras nuevas no hay `float` ni
  `double` ni `long`, y en Minecraft eso es la mayoría de los campos de estado.

## 5. Ejemplos concretos, no genéricos

- `SetEntityLookTargetSometimes$Ticker` (la clase real que usa el arnés de grafo) **pasa todas las
  cláusulas propias**; la rechaza su campo `final UniformInt`, porque `UniformInt` extiende
  `IntProvider` y declara interfaz. El bloqueo no es de `Ticker`: es del tipo de su campo.
- `BoundingBox` tiene 6 campos `int` y sería un layout de 6 ranuras… pero **no es `final` y tiene
  subclases** (`MutableBoundingBox`). Rechazarla es correcto: una instancia de la subclase no cabe en
  el layout del padre. Esto es exactamente lo que la regla «mundo cerrado» compra y por qué no puede
  ser «quitar la comprobación de `final`» sin más.

## 6. Lo que este trabajo **no** dice

- No hay ninguna clase traducida ni ejecutada por esto. Un layout aceptado es un contrato de campos.
- De las 165 aceptadas solo **una** tiene campos, y con dos `int`. El pipeline completo (layout →
  Rust → ejecutar) sigue sin una sola clase vanilla con estado ejecutándose.
- El contraste de parsers cubre 12 clases con ≤40 campos y ≤40 métodos; no es una prueba del parser
  completo.
- El perfil sigue sin modelar `long`/`float`/`double`/`byte`/`char`/`short`/`boolean`, herencia con
  campos, ni polimorfismo.

## 7. Qué se implementa después, en este orden

1. ~~**`final` → mundo cerrado**~~ — **hecho el 2026-11-06**: 6 → 165 clases y la primera con campos.
2. **Interfaces fuera del criterio de layout** (470): un campo no depende de las interfaces de su
   tipo. La clase sigue sin poder *ejecutarse* (despacho), pero su layout ya es describible.
3. **Refs sin cierre** (651 / 186 con campos): pasar de «grafo completo» a «layout por demanda»,
   anotando por clase qué falta para ejecutarla.
4. **Ranuras nuevas** para `J`/`F`/`D`/`Z`/`B`/`C`/`S`: sin esto, el punto 3 se queda en 186 clases.
5. **Herencia con campos** (3.525 clases bloqueadas por superclase): el layout pasa a ser
   «campos del padre + propios». Es el bloqueo más grande del JAR y hoy no está modelado.

Ninguno de los cuatro mueve `Main`; eso es A-03/A-05/A-06. Lo que hacen es que el 0/687 deje de ser
un número opaco y se convierta en un techo con nombre.

## 8. Cómo se reproduce

```bash
export JAVA_HOME=/ruta/al/jdk25
python3 mc-aot/tools/layout-profile-census.py --simulate --plan      # censo y plan
python3 mc-aot/tools/numeric_bridge_layout.py downloads/server-26.3-inner.jar \
    net/minecraft/server/players/SleepStatus --compiler mc-aot/target/release/mc-aot \
    --jar-sha256 a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6
python3 mc-aot/tools/layout-profile-census.py --class net.minecraft.world.level.levelgen.structure.BoundingBox
python3 mc-aot/tests/check-vanilla-layout-profile.py                 # prueba registrada (48)
```

La prueba falla si cambia el número de clases del JAR, el número o el hash de la lista de admitidas,
los dos contadores del censo que se fijaron (tipo no cerrado = 485, superclase = 3.525) o la tabla
del plan. Es a propósito: esas
cifras son la base de las decisiones de la sección 6.
