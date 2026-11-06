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
| Aceptadas por el perfil con grafo cerrado | **6** |
| De ellas, con campos de instancia | **0** |
| Controles negativos sobre bytes reales (quitar `final`, marcar abstracta, truncar, hash ajeno, clase ausente) | 5 rechazos correctos |
| Clases comparadas entre los dos parsers | 12, sin diferencias |

Las 6 aceptadas son `PreparableReloadListener$StateKey`, `Graph`, `MobEffectUtil`, `LongJumpUtil`,
`NoiseRouterData$QuantizedSpaghettiRarity` y `WaypointStyleAsset`. **Ninguna tiene campos**: son
clases de utilidades con métodos estáticos y constructor privado. Es decir, el primer layout sacado
de bytes oficiales es real pero **vacío**; no conviene presentarlo como «layouts de Minecraft».

## 2. Por qué el resto no entra (censo)

Primer bloqueo por clase, sobre las 7.762 (`--simulate` para el detalle):

| Cláusula que la bloquea primero | Clases |
|---|---|
| `clase-no-final` | 5.377 |
| `superclase` (no extiende `java/lang/Object`) | 1.527 |
| `clase-abstracta/interfaz/enum` | 379 |
| `nombre-fuera-del-perfil` | 343 |
| `interfaces` | 57 |
| `clinit` | 39 |
| `ref-fuera-del-perfil` | 14 |
| `estaticos` | 12 |

Esto desmiente la explicación que había escrita («casi todas tienen estáticos o no son `final`»):
los estáticos explican **12** clases, no casi todas. El muro es `final` y la superclase.

La razón de fondo es de diseño: el perfil exige que la clase sea cerrada (nada la extiende) y que su
padre sea `java/lang/Object`. En Minecraft casi ningún objeto cumple eso.

## 3. La separación que faltaba: layout ≠ ejecución

El verificador rechaza por cosas que **no describen el layout de un objeto**:

- `estaticos` y `clinit` son capacidad de **ejecución** (A-05). Un campo estático no ocupa el objeto.
- `interfaces` afectan al **despacho**, no a los campos.
- el **cierre de referencias** es una exigencia del arnés (el grafo debe estar completo), no del
  layout: el destino se puede describir cuando haga falta.

Al separarlas, el número deja de ser «0 y no hay camino» y pasa a ser una tabla de qué compra cada
relajación. Medido con `layout-profile-census.py --plan` (fijado en la prueba para que no derive):

| Paso | Clases | Con campos | Campos de instancia |
|---|---|---|---|
| Perfil actual de `numeric_bridge_layout.verify` | 6 | 0 | 0 |
| + estáticos y `clinit` fuera del criterio de layout | 9 | 0 | 0 |
| + `final` → tipo cerrado (ninguna subclase en el JAR) | 291 | 1 | 2 |
| + interfaces fuera del criterio de layout | 470 | 5 | 10 |
| + refs de instancia sin cierre (layout del destino bajo demanda) | **651** | **186** | **375** |

Lectura honesta de la tabla:

- Las dos primeras filas no cambian nada material: sin tocar `final` y la supercadena no hay objetos.
- El salto grande es el último: **186 clases con 375 campos de instancia** se pueden describir sin
  ninguna capacidad de ejecución nueva. Es el techo realista de A-02 fase 2 hoy.
- Quedan **309 clases con campos bloqueadas solo por `descriptor`**: `J`, `F`, `D`, `Z`, `B`, `C`, `S`.
  El puente numérico solo tiene ranura `Int` y referencias. Sin ranuras nuevas no hay `float` ni
  `double` ni `long`, y en Minecraft eso es la mayoría de los campos de estado.

## 4. Ejemplos concretos, no genéricos

- `SetEntityLookTargetSometimes$Ticker` (la clase real que usa el arnés de grafo) **pasa todas las
  cláusulas propias**; la rechaza su campo `final UniformInt`, porque `UniformInt` extiende
  `IntProvider` y declara interfaz. El bloqueo no es de `Ticker`: es del tipo de su campo.
- `BoundingBox` tiene 6 campos `int` y sería un layout de 6 ranuras… pero **no es `final` y tiene
  subclases** (`MutableBoundingBox`). Rechazarla es correcto: una instancia de la subclase no cabe en
  el layout del padre. Esto es exactamente lo que la regla «mundo cerrado» compra y por qué no puede
  ser «quitar la comprobación de `final`» sin más.

## 5. Lo que este trabajo **no** dice

- No hay ninguna clase traducida ni ejecutada por esto. Un layout aceptado es un contrato de campos.
- Las 6 clases aceptadas no tienen campos, así que el pipeline completo (layout → Rust → ejecutar) no
  ha ganado ni una clase vanilla con estado.
- El contraste de parsers cubre 12 clases con ≤40 campos y ≤40 métodos; no es una prueba del parser
  completo.
- El perfil sigue sin modelar `long`/`float`/`double`/`byte`/`char`/`short`/`boolean`, herencia con
  campos, ni polimorfismo.

## 6. Qué se implementa después, en este orden

1. **`final` → mundo cerrado** (291 clases): es análisis estático sobre el JAR que ya tenemos, y no
   cambia la semántica del puente: sigue sin haber subtipos, solo se admite como cerrada una clase
   que nadie extiende en el JAR. Requiere que el verificador consulte la tabla de subclases.
2. **Interfaces fuera del criterio de layout** (470): un campo no depende de las interfaces de su
   tipo. La clase sigue sin poder *ejecutarse* (despacho), pero su layout ya es describible.
3. **Refs sin cierre** (651 / 186 con campos): pasar de «grafo completo» a «layout por demanda»,
   anotando por clase qué falta para ejecutarla.
4. **Ranuras nuevas** para `J`/`F`/`D`/`Z`/`B`/`C`/`S`: sin esto, el punto 3 se queda en 186 clases.

Ninguno de los cuatro mueve `Main`; eso es A-03/A-05/A-06. Lo que hacen es que el 0/687 deje de ser
un número opaco y se convierta en un techo con nombre.

## 7. Cómo se reproduce

```bash
export JAVA_HOME=/ruta/al/jdk25
python3 mc-aot/tools/layout-profile-census.py --simulate --plan      # censo y plan
python3 mc-aot/tools/layout-profile-census.py --class net.minecraft.world.level.levelgen.structure.BoundingBox
python3 mc-aot/tests/check-vanilla-layout-profile.py                 # prueba registrada (48)
```

La prueba falla si cambia el número de clases del JAR, la lista de admitidas, los dos contadores del
censo que se fijaron (`final` = 5.377, superclase = 1.527) o la tabla del plan. Es a propósito: esas
cifras son la base de las decisiones de la sección 6.
