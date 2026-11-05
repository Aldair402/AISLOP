# Ruta propuesta: integrar log4rs sin fingir Log4j

`mc-aot/log4rs-prototype` usa log4rs 1.4.0, con lock propio; no está conectado a `multi-static-demo` ni a Eula. La comparación normaliza nivel/nombre/mensaje y no prueba la presentación vanilla. Ver su README y `analysis/log4rs-focused-regressions.log`.

## Recursos oficiales examinados

Bundle 26.3: `com/mojang/logging/1.7.12/logging-1.7.12.jar`, SHA-256 `3c7ac9742fa98c773275379eb1046c048b5d2ee989152a8c69e7ba696c3f8538`; `log4j2.xml` SHA-256 `460c415f60f7d0ee641e610a338af78acdcd139b2b65b6be903231febc2368dd`. Declara root INFO, filtro `NETWORK_PACKETS`, consola, `RollingRandomAccessFile` con políticas de tiempo e inicio y gzip, `Queue` y `Listener` Tracy. Un `EventSink` en archivo con eventos hex no es esta configuración.

## Pasos técnicos

1. Diseñar perfil explícito verificando origen, hashes y ausencia de sobreescrituras de configuración, propiedades y plugins incompatibles. No interceptar silenciosamente con un sink parcial. Mantener el perfil real traducido por separado.
2. Extender el ejecutor emitido para enlazar la dependencia con Cargo/lockfile y probar compilación atómica; el `multi-static-demo` actual invoca `rustc` directo. Evitar depender de rutas temporales del agente y no dejar binarios viejos si falla. Mantener el binario final sin JVM externa.
3. Añadir representación de loggers Java con identidad/nombre y llamadas SLF4J limitadas a firmas verificadas, incluyendo nombre del caller obtenido de `LogUtils.getLogger` a partir de los frames Java. Comprobar inicialización y llamadas reales, sin sustituir la clase completa por un no-op. Hay campo `FATAL_MARKER` y StackWalker en `<clinit>`.
4. Integrar valores Java que Eula pasa (`Path` y excepciones, incluido Throwable final y sus stack traces), conversión a cadena con efectos y reglas de escapes `{}`, enabled antes de cómputos perezosos; guardas para valores que el runtime no pueda representar. El fixture Rust de hoy es un mensaje conocido, no un Path traducido.
5. Modelar en orden los destinos y el filtro del XML y contrastar con Log4j real: zona local, reloj y nombres de hilos, formato visual, consola y file con rotación/compresión, cola y listener Tracy, filtros/markers mutable, niveles dinámicos, propagación y cierre. Si los destinos no equivalen, rechazar el perfil y no descartar eventos.
6. Crear probe Java→binario genuino que ejecute `Eula.class` sin reemplazar su cuerpo ni su logger por un stub; comparar éxito y errores de archivo, contenido de logs y efectos de archivo. Después abordar `Main`/ForkJoinPool, workers, excepciones y shutdown. Un probe Eula no equivale a arrancar servidor.

La suite integral aprobada tiene 284 etapas, incluidos los cuatro pasos de log4rs (`analysis/full-regressions-log4rs.log`); la anterior tenía 280 (`analysis/full-regressions-reflection-sort-retry.log`). El oráculo Java de excepciones de Eula se ejecutó por separado y se incorporó después a `run-regressions.sh`; no formó parte de esas 284 etapas. 0/7.762 clases certificadas, meta 3.881.

## Oracle real de excepción en Eula
`analysis/eula-throwable-oracle.log`: al crear `eula.txt` como directorio, Eula Java oficial devuelve false, emite `Failed to load eula.txt` sin Throwable y luego `Failed to save eula.txt` con `java.nio.file.FileSystemException` asociado al evento. Por tanto, comparar únicamente el texto omite un efecto esencial; el prototipo aún no soporta esa ruta. Prueba reproducible `mc-aot/tests/check-eula-throwable-oracle.py` (solo Java; incorporada a la suite después de la integral de 284 etapas).

## Uso directo de logging en el JAR interno
`python3 mc-aot/tools/inspect-logging.py > analysis/logging-direct-calls.tsv 2> analysis/logging-direct-signatures.tsv` recorre las 7.762 clases internas. Detecta **1.105 invocaciones directas en 326 clases**, incluidas 283 a `LogUtils.getLogger`, 107 a `warn(String,Object,Object)`, 89 a `warn(String,Object)` y al menos 98 con un descriptor que declara `Throwable`. También encuentra `Object[]`, markers, `defer(Supplier)` y `LoggingEventBuilder`. Son sitios de bytecode, no frecuencias dinámicas ni cobertura completa: llamadas por métodos auxiliares, reflexión y dependencias externas no están contadas. Priorizar los perfiles por rutas reales y evitar asumir que todos los argumentos son strings o que la excepción forma parte del mensaje.
