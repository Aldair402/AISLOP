# Math.min/max flotante: un bloqueo menos, no una clase completa

`ChestLidController.tickLid()` llama `Math.max(FF)F` y `Math.min(FF)F`. Antes,
`class-demo-rs` rechazaba la primera llamada. Se implementaron las cuatro firmas
`(FF)F` y `(DD)D` para `min` y `max` en el backend numérico multiclase. El
runtime propaga NaN y ordena el cero negativo antes del positivo, en vez de
usar directamente los métodos de Rust, cuyo comportamiento con NaN difiere.

`check-math-float-minmax.py`: 1.444 comparaciones de pares de bits, incluyendo
ambos ceros, subnormales, infinitos, NaN y números aleatorios, con resultados
contrastados contra Java 25. El nativo corre con `PATH` sin Java. Se comparan
bits canónicos de NaN, no la preservación del payload de cada NaN. La prueba está
registrada en la integral; su ejecución aislada pasó. `cargo test`: 33/33.

**No se cuenta `ChestLidController` como completa.** Con el JAR interior, la
siguiente causa es la clase `org/joml/Vector3f` ausente del classpath de ese JAR.
Con el bundle oficial, que sí incluye JOML, la traducción llega hasta
`Mth.<clinit>` → `Util.<clinit>` → `Util.makeExecutor` y rechaza `new
java/util/concurrent/ForkJoinPool`. No se omiten esos inicializadores para
aparentar que pasa: su semántica sigue siendo necesaria.

El censo de generación también fue corregido para usar la primera línea del error
(causa raíz), no la última línea de contexto `al compilar`. Un fallo interno del
compilador aborta el censo; no se cuenta como bloqueo normal. Generar Rust no es
compilar ni demostrar comportamiento; no usar ese censo como contador de clases
completas. Los resultados de la nueva integral y del censo siguen pendientes.
