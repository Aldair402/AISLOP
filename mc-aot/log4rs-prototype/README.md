# Prototipo aislado de sink log4rs

No es un backend del traductor, no ejecuta bytecode Java y no permite arrancar Minecraft. El archivo de salida contiene eventos de diagnóstico normalizados en `LEVEL|hex(nombre)|hex(mensaje)`, no el formato de `logs/latest.log`. No configura ni reemplaza automáticamente Log4j. `log4rs 1.4.0` es una implementación Rust de logging, no un proveedor binario SLF4J ni un intérprete de XML Log4j. El lockfile de este directorio fija las dependencias del prototipo; no modifica el ejecutable emitido por mc-aot.

`EventSink` usa un `FileAppender` real con log4rs y raíz configurable. Solo recibe nombres y mensajes Rust UTF-8 válidos, argumentos `String` o null ya convertidos y `{}` **sin escapes de barra invertida**; se rechazan explícitamente templates con `\`. No acepta `Throwable`, arreglos, `Supplier`, objetos Java arbitrarios, referencias Java, Unicode con sustitutos aislados ni markers como objetos Java. La cadena `Path` en el fixture es el resultado conocido `eula.txt`; no implementa `Path.toString` general. El archivo se abre en modo append; log4rs puede crear directorios y su semántica de apertura no está certificada como la de Log4j. Rutas con expansión especial de log4rs se rechazan. Errores del appender se propagan al llamador del prototipo (probado con `/dev/full`); eso tampoco demuestra la política de errores de Log4j.

El método opt-in `emit_minecraft_root` ensaya el filtro `NETWORK_PACKETS` del XML oficial: deniega el marcador o un descendiente del mismo. `Marker` es una vista inmutable construida por el llamador, no la API Java mutable de marcadores; el grafo recorrido se limita a 10.000 nodos. No procesa el XML ni los otros filtros/configuraciones. El método `enabled` solo evalúa el nivel, en los casos observados; en el oráculo raíz oficial `isInfoEnabled(marker)` devuelve true incluso para un marker que luego se filtra.

## Validación

- `tests/check-log4rs-prototype.py`: 1.680 eventos (niveles, logger, texto y argumentos de cadenas/null), 120 consultas `isEnabled`, frente a SLF4J/Log4j oficiales con una configuración común de prueba. El sink Rust usa el archivo real de log4rs y el Java captura eventos con un appender de prueba. La comparación elimina deliberadamente timestamps, hilo, formato visual, rotación y los demás destinos.
- `tests/check-log4rs-eula-event.py`: ejecuta `net.minecraft.server.Eula` original en Java y captura el WARN de un archivo ausente. Un fixture Rust emite el evento conocido y ambos registros normalizados coinciden. **Eula solo se ejecuta en Java**, no hay Eula traducida ni acoplamiento con log4rs.
- `tests/check-minecraft-log-config-oracle.py`: extrae el XML oficial del JAR de Mojang, conserva su filtro y nivel, sustituye los destinos por un appender de captura y compara el fixture Rust para INFO/WARN, DEBUG y `NETWORK_PACKETS` directo/heredado. No prueba consola, archivos, cola, Tracy ni rotación originales.
- `cargo test`: pruebas de append, filtros, escapes, rutas, errores de escritura y 2.000 registros concurrentes íntegros. No certifica el orden bajo concurrencia ni toda la semántica Java.

Ejecutar con JDK 25 y Rust/Cargo:

```sh
cargo test --locked --manifest-path mc-aot/log4rs-prototype/Cargo.toml
python3 mc-aot/tests/check-log4rs-prototype.py
python3 mc-aot/tests/check-log4rs-eula-event.py
python3 mc-aot/tests/check-minecraft-log-config-oracle.py
```

El inventario estático del JAR interno localiza 1.105 invocaciones directas de logging en 326 clases, incluidas al menos 98 con `Throwable` explícito; no son frecuencias de ejecución (`analysis/logging-direct-signatures.tsv`). En Eula real, una escritura fallida adjunta `FileSystemException` al evento (`analysis/eula-throwable-oracle.log`).

## Antes de integrar

Hace falta un contrato de sustitución explícito y controlado por perfil; conectarlo a las llamadas Java traducidas y conservar identidad y nombres de logger/caller, inicialización, niveles dinámicos, `Throwable`, sustitución de parámetros, markers mutables y seguridad en hilos. Para reproducir el perfil vanilla también faltan el formato real con hora e hilo, consola, `logs/latest.log`, rotación diaria/al iniciar y gzip, GUI Queue, listener Tracy, configuración externa y cierre. Donde no haya equivalencia comprobada, rechazar, no simular ni descartar entradas silenciosamente. Nunca afirmar compatibilidad de Log4j o arranque por estos fixtures.
