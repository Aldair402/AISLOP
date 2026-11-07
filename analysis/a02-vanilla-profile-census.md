# A-02 fase 2 — el perfil de layouts medido contra el JAR oficial

Fecha: 2026-11-07. Este documento sustituye a `analysis/a02-layout-validation.md` en todo lo
relativo al perfil, y corrige dos cifras que se publicaron antes y estaban mal:

- «0 de 687 candidatas»: el log tiene una sola línea, no dice de dónde salieron las 687 ni qué
  cláusula fallaba en cada una, y el verificador **sí** aceptaba clases del JAR.
- «6 aceptadas, ninguna con campos»: cierto durante unas horas, pero la explicación asociada («el
  muro son los estáticos», «el muro es `final`») no describía el problema real.

## 1. Lo que hay hoy, medido

`mc-aot/tests/check-vanilla-layout-profile.py` (registrada en `run-regressions.sh:48`) comprueba
cinco cosas, y ninguna es decorativa:

1. **Censo** de las 7.762 clases del JAR oficial con el parser puro-Python de `classfile-surface.py`
   aplicando las mismas reglas que el verificador.
2. **Verificador real** (`mc-aot inspect`) sobre las clases que el censo declara describibles, con el
   SHA-256 del classfile y la comparación campo a campo con el classfile.
3. **Acuerdo en los dos sentidos**: una muestra de bloqueadas debe ser rechazada por el verificador
   con el motivo que el censo nombró.
4. **Contraste de parsers**: Rust y Python, escritos por separado, deben coincidir en flags, campos y
   métodos de clases reales (12 clases, 0 diferencias).
5. **Controles negativos sobre bytes reales** y el contrato de subclases (§5).

Resultado actual:

| Medida | Valor |
|---|---|
| Clases en el JAR oficial | 7.762 |
| **Describibles** (layout completo, sin bloqueo fatal) | **2.611** |
| De ellas, **con campos de instancia** | **1.564** |
| Campos de instancia descritos | **4.048** |
| Clases con campos que además son `record` | 636 |
| Con campos `long`/`float`/`double` | 254 |
| Controles negativos sobre bytes reales | 4 rechazos + 1 contrato |

Ejemplos que la prueba lee en el log:

| Clase | Layout | Por qué es cerrada |
|---|---|---|
| `server/players/SleepStatus` | `int activePlayers`, `int sleepingPlayers` | no `final`, nada la extiende |
| `world/level/BlockEventData` | `ref pos`, `ref block`, `int paramA`, `int paramB` | tiene subclases: se describe igual |
| `world/level/levelgen/structure/BoundingBox` | 6 `int` | idem |
| `advancements/AdvancementHolder` | 2 `ref` | `record`: base externa `java.lang.Record` |
| `commands/arguments/coordinates/LocalCoordinates` | 3 `double` finales | `record`; ranura ancha desde el classfile |

## 2. La separación que hace posible el número: layout ≠ ejecución

El perfil rechazaba por cosas que **no describen un objeto**:

- **Campos estáticos** y **`<clinit>`**: no ocupan la instancia. Son capacidad de ejecución (A-05).
- **Interfaces**: afectan al despacho, no a los campos.
- **Destinos de referencia**: el layout de una ranura es *una referencia*. Si el destino no se puede
  describir todavía, eso bloquea **leer por esa ranura**, no escribir el layout de esta clase.
- **`final` en un `int`**: es una restricción de escritura, no otra ranura. Se acepta y se anota
  (`final: true`) para que el traductor pueda negar la escritura en vez de olvidarla.

Todo eso se anota ahora en `execution_blockers` (por clase), y el layout sale igual. Entre las 2.611
describibles: 1.552 tienen campos estáticos, 1.410 tienen `<clinit>` y 1.328 declaran interfaces.

Lo que **sí** sigue siendo fatal, porque el layout no puede representarlo:

| Bloqueo fatal | Clases |
|---|---|
| referencia a un tipo del que no hay bytes en el JAR (`String`, `Map`, `List`, `Codec`…) | 2.238 |
| ~~sin ranura~~ (`int`/`boolean`/`byte`/`char`/`short`/`long`/`float`/`double`) | **0**: las ocho ranuras existen desde el 2026-11-07 |
| arrays (`[B`, `[J`, `[F`…) | 40 |
| cadena de superclases fuera del JAR (`DataFix` 275, `Schema` 122, `RuntimeException` 29, `jfr/Event` 12, Guava 11) | 449 |
| referencia no final (sin el opt-in `MutRef`) | 569 |
| `volatile` | 23 |
| nombre fuera de `net/minecraft` | 343 |

## 3. Herencia: prefijo, no herencia implícita

El layout de una clase es **la cadena completa**: campos de los ancestros desde `Object`, en orden,
y después los propios. `own_field_count` dice cuántos son de la clase.

La razón no es estética: si un campo declarado en el padre tiene el mismo índice en el layout de
cualquier descendiente, el traductor puede resolver un acceso por la clase declarante y acertar
también en un objeto de la subclase. Y `attach` exige que el nombre de la clase del objeto sea
exactamente `layout.class`, así que un objeto de una subclase **sin layout** falla cerrado en vez de
leerse con el layout del padre.

Consecuencia: **la regla de tipo cerrado dejó de ser necesaria para la seguridad**. Se conserva como
etiqueta informativa (`closed_by`: `final`, `no-subclasses` o `has-subclasses`) porque dice mucho de
lo que el traductor puede asumir, pero ya no rechaza. La prueba lo fija: compilar una subclase real
de `SleepStatus` contra el classfile oficial **no cambia el layout**, solo la etiqueta.

## 3 bis. Las ocho ranuras primitivas (implementadas el 2026-11-07)

`NumericGraphSlot` tenía `Int`, `Ref` y `MutRef`. Ahora tiene una ranura por tipo
declarado — `Int`, `Bool`, `Byte`, `Char`, `Short`, `Long`, `Float`, `Double`, `Ref`,
`MutRef` — porque `boolean`/`byte`/`char`/`short` comparten almacenamiento físico con
`int` (la JVM también los ensancha) pero el traductor necesita saber **qué anchura
recortar** al escribir. La comprobación es explícita (`slot_matches_value`), no por
discriminante del heap.

En el almacenamiento compartido, `concurrent_heap::Value` y `ExternalValue` ganan
`Long(i64)`, `Float(u32)` y `Double(u64)`. `Float`/`Double` guardan **bits** para
conservar `Eq`: la igualdad de un `Value` es de representación, no IEEE (+0.0 y -0.0
difieren; NaN es igual a sí mismo). La semántica de coma flotante se queda en la pila
del intérprete, que ya tenía `V::F`/`V::D`.

Prueba: `mc-aot/tests/check-numeric-wide-slots.py` (registrada en `run-regressions.sh`).
Compila una clase con los ocho tipos, traduce su bytecode, publica el objeto por el
puente y compara **huellas de bits** con el mismo programa en Java 25:

| Huella | Java 25 | Rust por el puente |
|---|---|---|
| `long` (xor de mitades) | 256 | 256 |
| `double` (bits xor) | 1.073.872.896 | 1.073.872.896 |
| `float` (bits) | 1.069.547.520 | 1.069.547.520 |
| `int+boolean+byte+char+short` | −2.844 | −2.844 |

Además: escribir `long`/`float`/`int` por el puente se observa desde el bytecode numérico
traducido (no solo por el mismo camino de lectura), escribir un `int` en la ranura `long`
(o un `double` en `float`, o un `long` en `int`) se rechaza, y un layout con una ranura
cambiada no se puede ni adjuntar. El binario se ejecuta sin Java en `PATH`.

## 4. Bases externas: una excepción con prueba, no por conveniencia

1.484 clases son `record` y su superclase es `java.lang.Record`, que no está en el JAR. Se admite
como base **sin estado** (`EXTERNAL_EMPTY_BASES`), y la prueba lo verifica por reflexión con JDK 25:
`java.lang.Record` declara **0** campos de instancia. No se admite `java/lang/Enum` (tiene `name` y
`ordinal`) ni `RuntimeException` (tiene `message`, `cause`, `stackTrace`): esas cadenas siguen fuera.

## 5. Controles negativos (sobre bytes reales, no fixtures)

1. Marcar la clase como interfaz → rechazo.
2. Truncar el classfile → rechazo.
3. Hash del JAR que no corresponde → rechazo.
4. Clase ausente → rechazo.
5. **Compilar una subclase real** de `SleepStatus` contra el `.class` oficial → el layout es
   **idéntico** y `closed_by` pasa a `has-subclasses`. Si el layout cambiara, la herencia por prefijo
   sería una mentira.

Y en `check-numeric-bridge-layout.py` (fixtures, 16 rechazos) se fija el resto del contrato: `Tag`
interfaz, `volatile`, los siete descriptores primitivos sin ranura, arrays, `String`, referencia
mutable sin opt-in, ausente, duplicados, multi-release, hash; y los positivos: herencia con prefijo,
estáticos/`<clinit>`/interfaces como bloqueos de ejecución, `int final` anotado, ciclos de
referencias, `closed_by` en sus tres valores.

## 6. Lo que este trabajo **no** dice

- **Cero clases traducidas o ejecutadas** por todo esto. Un layout aceptado es un contrato de campos.
- Los 4.048 campos son una descripción: de los ocho primitivos ya hay lectura y escritura probadas desde
  bytecode traducido, pero solo en fixtures (`check-numeric-wide-slots.py`), no en clases vanilla.
- El `attach` de Rust sigue exigiendo layouts declarados a mano en el arnés: la ruta «layout generado
  → Rust → ejecutar» está probada solo con fixtures (`Node`, `TickTask`, `Wide`), no con estas 2.611.
- El contraste de parsers cubre 12 clases con ≤40 campos y ≤40 métodos.
- Sigue sin modelarse: arrays como campo, referencias a tipos fuera del JAR, referencias mutables por
  defecto, GC, estáticos compartidos y `Main`.

## 7. Qué se implementa después, en orden de coste medido

1. ~~**Ranuras nuevas**~~ — **hecho el 2026-11-07**: 2.161 → **2.611** describibles, 1.114 → **1.564**
   con campos, 2.469 → **4.048** campos; con prueba diferencial contra Java 25.
2. **Referencias a tipos del JAR de librería** (`java/lang/String`, `Map`, `List`, `Codec`): 1.839
   clases. No es un cambio de perfil: es *soportar* esos tipos (colecciones, cadenas como valor,
   serialización), y por eso no se relaja la regla a cambio de un número.
3. **Cadenas fuera del JAR** (`DataFix`, `Schema`, excepciones): 449 clases. Mismo argumento: hacen
   falta esas bases, no una excepción nueva.
4. **Referencias mutables por defecto** (569) y `volatile` (23): decisión de B (Q-AB-1/Q-AB-2).

Ninguno de los cuatro mueve `Main`; eso es A-03/A-05/A-06 y B-03/B-04/B-05.

## 8. Cómo se reproduce

```bash
export JAVA_HOME=/ruta/al/jdk25
python3 mc-aot/tools/layout-profile-census.py --plan
python3 mc-aot/tools/layout-profile-census.py --class net.minecraft.world.level.BlockEventData
python3 mc-aot/tools/numeric_bridge_layout.py downloads/server-26.3-inner.jar \
    net/minecraft/server/players/SleepStatus --compiler mc-aot/target/release/mc-aot \
    --jar-sha256 a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6
python3 mc-aot/tests/check-vanilla-layout-profile.py
```

La prueba falla si cambia el número de clases del JAR, las tres cifras del censo (2.611 / 1.564 /
4.048), el acuerdo censo↔verificador, la lista de bases externas sin estado o cualquiera de los
controles negativos. Es a propósito: esas cifras son la base de las decisiones de la sección 7.
