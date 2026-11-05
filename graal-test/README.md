# Prueba real: Minecraft 26.3 y GraalVM Native Image

## Resultado (31 de octubre de 2026)

- GraalVM Community **25.0.2**, descargado temporalmente desde su release oficial de GitHub y verificado con el SHA-256 publicado: `e0be791c8fda4d03b6b0a0cb824fef3149736170057b3a515252b44419606af0`.
- El JAR oficial del servidor se ejecutó en **la JVM de GraalVM** con `--help` y mostró sus opciones. Es una prueba de arranque del programa Java, no del servidor completo ni de un binario nativo. Véase `java-help.log`.
- `build.sh` extrajo y verificó los hashes SHA-256 del JAR interno y sus 39 bibliotecas, e inició Native Image sobre `net.minecraft.server.Main`.
- La compilación **no terminó**: se detuvo por el límite de tiempo de 300 segundos (código 124), después de la etapa de inicialización. Se limitó el heap del compilador a 1100 MB y se usaron dos hilos en una máquina con unos 2 GB de memoria. No hay binario nativo del servidor. El log está en `native-build.log`. No se puede concluir que la memoria sea la causa exacta ni que Minecraft 26.3 sea incompatible con GraalVM.
- No se añadieron metadatos específicos de reflexión, recursos y otras funciones dinámicas de 26.3: aunque se complete la compilación, hará falta probar y posiblemente ajustar la imagen antes de poder considerarla funcional.
- No se aceptó la EULA, no se creó ningún mundo y no se inició el servidor para jugar.

### Prueba adicional de mc-aot

Con la JVM Java 25 se compararon 20 métodos reales de Minecraft con los binarios del traductor: **2,720 resultados coincidieron** en 136 conjuntos de entradas, incluidos límites y valores aleatorios. Para división por cero se comprobó la categoría del error, no el mecanismo de excepción. Esto no valida el servidor entero. Código: `MthReference.java` y `compare-mth.py`; resultado: `mth-comparison.log`.

## ¿Qué hace GraalVM?

Native Image transforma bytecode Java y dependencias alcanzables en un ejecutable nativo con un runtime de GraalVM, sin necesitar una JVM externa para ejecutarlo. **No traduce el servidor a Rust** y no garantiza que sea más rápido. Para Minecraft, la carga dinámica, la reflexión, los recursos y las bibliotecas nativas pueden requerir configuración y ajustes adicionales.

## Repetir la compilación en Linux x86-64

1. Instala GraalVM Community JDK 25 con Native Image y las herramientas C de tu sistema (incluyendo gcc y cabeceras de desarrollo), además de Python 3.
2. Desde esta carpeta, apunta `GRAALVM_HOME` al JDK e inicia la compilación. `BUILD_HEAP` es el máximo para el heap del compilador, no la memoria total del proceso:

```bash
export GRAALVM_HOME=/ruta/a/graalvm
set -o pipefail
BUILD_HEAP=4g BUILD_THREADS=2 ./build.sh 2>&1 | tee native-build.log
```

El resultado, si llega a generarse, será `output/minecraft-26.3-native`. La configuración actual es solo una **primera prueba**, sin metadatos de compatibilidad específicos y con `-O0` para acelerar la compilación; no es una compilación de rendimiento. Puede fallar, necesitar mucho más tiempo o memoria, o producir un ejecutable que no funcione correctamente. Un archivo anterior con el mismo nombre podría permanecer si una compilación posterior falla: verifica siempre el código de salida. La imagen se compila para la máquina objetivo seleccionada por GraalVM; no se garantiza que funcione en otros sistemas o procesadores.

El script usa el JAR de `../downloads/` por defecto. Puedes cambiarlo con `SERVER_JAR=/ruta/server.jar`, siempre que sea un bundle moderno con `META-INF/libraries.list`, `versions.list` y `main-class`. No acepta la EULA automáticamente. Revisa los términos de Mojang y de las bibliotecas antes de ejecutar o redistribuir resultados.

Para repetir la comparación con los binarios Linux x86-64 incluidos:

```bash
JAVA_HOME="$GRAALVM_HOME" python3 compare-mth.py
```

Esta prueba requiere que los 20 binarios de `../mc-aot/examples/` sean ejecutables compatibles con tu equipo. En otros sistemas compílalos de nuevo siguiendo `../mc-aot/README.md`.

## Fuentes

- [GraalVM Native Image](https://www.graalvm.org/latest/reference-manual/native-image/)
- [GraalVM Community releases](https://github.com/graalvm/graalvm-ce-builds/releases)
- [Proyecto previo de servidor nativo](https://github.com/hpi-swa/native-minecraft-server): declara compatibilidad únicamente con Minecraft 1.18.2, no 26.3.
