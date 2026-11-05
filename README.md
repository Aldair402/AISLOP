# Minecraft JAR → binario nativo: punto de partida

> **Trabajo en equipo:** ver [`TODO.md`](TODO.md) para repartir tareas, archivos y revisiones sin duplicar trabajo.

> **Roadmap activo:** ver [`ROADMAP.md`](ROADMAP.md). La integración de log4rs queda aparcada; no se cambia el criterio de no simular logging. Suite integral más reciente: **306 etapas, exit 0**, `analysis/full-regressions-a03.log`; no certifica clases.

## Preparación tras clonar

El repositorio no distribuye los JAR de Mojang o de descompiladores, ni los ejemplos generados. Para reproducir los experimentos, descarga el bundle oficial y verifica ambos hashes:

```sh
mkdir -p downloads
curl -fL https://piston-data.mojang.com/v1/objects/33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c/server.jar -o downloads/server-26.3.jar
printf '%s  %s\n' 33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c downloads/server-26.3.jar | sha1sum -c -
python3 - <<'PYCODE'
import pathlib, zipfile
with zipfile.ZipFile('downloads/server-26.3.jar') as z:
    pathlib.Path('downloads/server-26.3-inner.jar').write_bytes(z.read('META-INF/versions/26.3/server-26.3.jar'))
PYCODE
printf '%s  %s\n' a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6 downloads/server-26.3-inner.jar | sha256sum -c -
```

Se necesitan Rust/Cargo y JDK 25. Los ejecutables de ejemplo pueden regenerarse con `bash mc-aot/build-examples.sh`; para la integral, define `JAVA_HOME` y ejecuta `bash mc-aot/run-regressions.sh`. Los informes y logs son evidencia de ensayos anteriores, no certificación del servidor.

## Evaluación y prototipo de log4rs

`log4rs` puede servir como motor nativo, pero no sustituye directamente SLF4J/Log4j ni la configuración vanilla. Se creó `mc-aot/log4rs-prototype` con un `FileAppender` real, independiente del traductor: 1.680 eventos normalizados y 120 consultas de nivel coinciden con SLF4J/Log4j oficiales bajo configuración controlada; cinco tests Rust prueban errores de escritura y 2.000 registros concurrentes entre otros. Se comparó también el WARN de `Eula.class` real ejecutado **solo en Java** con un fixture Rust, y el filtro `NETWORK_PACKETS` del XML oficial con un modelo limitado. Detalles, guardas y reproducción en `mc-aot/log4rs-prototype/README.md`, `analysis/log4rs-focused-regressions.log` y `analysis/next-log4rs-integration.md`.

El prototipo no procesa XML ni cubre los formatos/destinos, rotación, marcadores mutables, `Throwable` o llamadas Java de Minecraft; no está conectado a Eula, Main ni al backend. No demuestra logger vanilla ni arranque. **0/7.762 clases completas certificadas; objetivo 3.881**. La suite integral con los cuatro pasos de log4rs terminó con **284 etapas y exit 0** (`analysis/full-regressions-log4rs.log`). El oráculo adicional de excepciones de Eula se ejecutó focalizadamente y se añadió después a la suite; no forma parte de esa integral.


## Actualización: reflexión, arrays y diagnóstico del proveedor real

Se implementaron perfiles acotados de `Member.getModifiers/getDeclaringClass`, los doce predicados de `Modifier`, `Class.getModifiers` usando `InnerClasses`, `AccessibleObject.isAccessible/setAccessible(false)`, `InternalError`, `String.toCharArray` y `Arrays.sort(char[])`. Sus pruebas diferenciales Java 25 registran respectivamente 160, 4.096, 80, 160, 81, 100 y 350 casos. `setAccessible(true)` y `Matcher.matches()` sobre un receptor no nulo abortan explícitamente; no se simula accesibilidad ni coincidencias regex. Estas rutas no constituyen reflexión ni regex generales.

El límite de clases estáticas sigue siendo 256 por defecto; `MC_AOT_MAX_STATIC_CLASSES` permite **opt-in de 1 a 4.096**, sin garantizar que un programa de ese tamaño compile ni cambiar el resto de límites. Un fixture con 261 clases y límite 300 comparó 41 resultados con Java; límites inválidos se rechazan. El indexador y grafo procesaron las 7.762 clases del JAR oficial sin errores estructurales (`analysis/innerclasses-index-audit.log`); eso prueba lectura, no equivalencia ni cobertura completa.

Con classpath cerrado, proveedor Log4j registrado y límite 512, el probe más reciente de Eula se detiene al compilar `Enum.valueOf(Class,String)` en `ThreadNameCachingStrategy` (`analysis/real-eula-matcher-guard-attempt.log`). No se ha validado el logger ni se ha arrancado el servidor; `Main` continúa bloqueado en `ForkJoinPool`, y Rayon sigue fuera del backend principal. **0/7.762 clases completas certificadas; meta 3.881.** La suite integral corregida terminó con **280 etapas y exit 0**, incluidas 58+25 pruebas Rust y los nueve tests nuevos (`analysis/full-regressions-reflection-sort-retry.log`). Un intento previo detectó una expectativa obsoleta en la prueba de guarda de duración, corregida para verificar el aborto en ejecución (`analysis/full-regressions-reflection-sort.log`); ninguna de las pruebas certifica una clase completa.


## Continuación: Eula compilada, ejecución bloqueada y perfiles nuevos

En `analysis/real-eula-service-provider-attempt.log`, el probe de Eula con el bundle oficial **compila**, Java 25 devuelve `1` y el ejecutable nativo se detiene con código 2 al intentar cargar el proveedor real `org/apache/logging/log4j/core/impl/Log4jProvider`, no registrado para reflexión. **No se ejecutó Eula satisfactoriamente ni se arrancó el servidor**. Al registrar expresamente ese proveedor mediante `MC_AOT_EULA_EXTRA_REFLECT_CLASSES`, la compilación avanza hasta `Member.getModifiers()` en Log4j (`analysis/real-eula-member-cast-attempt.log`), todavía sin binario en ese perfil. No se simula el logger.

Se añadieron perfiles contrastados: `IdentityHashMap` por identidad con vista viva `Collections.newSetFromMap` (81 casos; `iterator` y fuentes `addAll` no admitidas abortan), `Arrays.copyOf(Object[],int)` (256), `StringBuilder.append(CharSequence,int,int)` (2.430), siete `TimeUnit` con saturación (2.156), `ByteArrayInputStream(byte[])` sobre array mutable (243), `URISyntaxException` (120), y `Character.isWhitespace(char)` exhaustivo (65.536, tabla SHA-256 `b28cdc46e4d2bccf3eb3945a521082b45b4102e451bd4276941305781006dcd2`). También se contrastaron `Integer.toHexString`, casts y consultas URI limitadas a CommonLinks, `emptySet`, `HashMap(int)`, casts `Member`, `String.contains` y jerarquía y contexto de cargadores. Los registros están en `analysis/*-validation.log` y los 20 tests añadidos están integrados en `mc-aot/run-regressions.sh`.

Las rutas no verificadas siguen fallando explícitamente: `System.identityHashCode` no nulo, `Executors.defaultThreadFactory`, URL real y muchas operaciones de reflexión/streams. El cargador de contexto mutable solo existe en el hilo principal y admite null, aplicación y plataforma; el valor inicial exige `MC_AOT_STANDARD_CONTEXT_LOADER=1`, salvo que se haya asignado explícitamente. `ClassLoader.getParent` y el cargador de plataforma requieren `MC_AOT_STANDARD_SYSTEM_LOADER=1`. `ByteArrayInputStream` no cubre todos sus constructores u operaciones, y la copia/colecciones no constituyen una implementación general de Java.

**Main continúa bloqueado en ForkJoinPool; Rayon sigue desconectado del backend principal. Sin servidor nativo y sin clases completas certificadas: 0/7.762; objetivo 3.881.** La integral anterior terminó con **271 etapas y exit 0**, incluidas 58+25 pruebas Rust (`analysis/full-regressions-identity-timeunit.log`); la anterior aprobada tiene 251 etapas (`analysis/full-regressions-array-profile-retry.log`).


## Estado de continuación: perfiles adicionales y límites

El probe de Eula con el bundle y las bibliotecas oficiales avanzó por compilación hasta `new java/util/IdentityHashMap` dentro de `ParameterFormatter.createDejaVu` (`analysis/real-eula-primitive-array-class-attempt.log`). Terminó con error; **no ejecutó Eula ni arrancó el servidor**. El formatter de Log4j también requiere zona y locale predeterminados: las operaciones de formato, `withZone` y `ofPattern` fuera del perfil se rechazan explícitamente, al igual que `StringBuilder.append(double)`, `SimpleDateFormat` y `WeakHashMap` no modelados.

Nuevos diferenciales frente a Java 25: pipelines `StackWalker.map/dropWhile/findFirst` (160 casos y 182 con StackLocator oficial), `StringBuilder` capacidad/coder/ciclo (370), Unicode `Character.toUpperCase(char)` exhaustivo (65.536), casts y boxing Double/Short/Character, `Date.toInstant` con extremos i64 (214), `Class.isArray` (81), literales de arrays primitivos (80) y `Collection` con colecciones, vistas y una implementación propia (100). Otros tests cubren `Math.addExact`, CharSequence, búsquedas de cadenas y guardas. Los resultados y limitaciones están en `analysis/*-validation.log` y `mc-aot/tests/`.

Se integraron 26 tests adicionales en `mc-aot/run-regressions.sh`. La primera integral detectó una guarda obsoleta: ahora se prueba el rechazo de `BigInteger` en vez del cast `Double` ya soportado (`analysis/full-regressions-array-profile.log`). La nueva integral terminó con exit 0 y **251 etapas**, incluidas las 26 pruebas añadidas (`analysis/full-regressions-array-profile-retry.log`); el registro previo de 225 etapas corresponde a una revisión anterior (`analysis/full-regressions-final-callback.log`).

**Main sigue bloqueado en ForkJoinPool; Rayon todavía no está conectado al backend principal. No hay servidor nativo ni clases completas certificadas: 0/7.762, frente al objetivo de 3.881.** Ningún diferencial parcial equivale a certificar una clase.


> **Estado actual:** el servidor aún no arranca ni hay un binario nativo completo. El último intento de `Main`, con `MC_AOT_DISABLE_JFR=1`, se detiene al compilar `ForkJoinPool`. Los prototipos de hilos y heap compartido no están integrados en el backend. Véase `PLAN-ARRANQUE.md` en la raíz y `analysis/main-multi-static-attempt.log`.

**Cobertura:** hay 7 762 clases en el JAR interno; la meta es validar completamente 3 881. Actualmente hay **0 clases completas certificadas**: las pruebas parciales por método no equivalen a una clase completa. El adaptador experimental de `ForkJoinPool` usa Rayon, pero aún no está conectado al backend principal ni reproduce todo el ciclo de vida de los workers. Un intento anterior de compilar Eula con bibliotecas reales se detuvo en `new java/io/PrintStream` del logger; las pruebas con stubs no demuestran el arranque.

Esta carpeta prepara el análisis del servidor oficial **Minecraft Java Edition 26.3**, la última versión estable indicada por el manifiesto oficial consultado el 31 de octubre de 2026. Incluye ahora `mc-aot/`, un primer traductor experimental para métodos muy simples de Minecraft. Todavía no es un servidor nativo; consulta [su guía](mc-aot/README.md).

## Archivos

- `downloads/server-26.3.jar`: JAR oficial distribuido por Mojang (62 294 556 bytes). SHA-1 comprobado contra el manifiesto: `33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c`.
- `downloads/server-26.3-inner.jar`: servidor real extraído del bundle. SHA-256 comprobado contra `META-INF/versions.list`: `a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6`.
- `tools/cfr-0.152.jar`: descompilador CFR. MD5 comprobado contra su página oficial: `8a85ada8cec494121246805a5562b82b`.
- `tools/vineflower-1.12.0.jar`: descompilador Vineflower. SHA-1 comprobado contra Maven Central: `85570609a0a5941a7d2918b6260b209de810f66f`.
- `analysis/version.json`: metadatos oficiales de la versión.
- `analysis/sample/decompiled/net/minecraft/server/Main.java`: muestra descompilada con CFR. Se generó con solo esa clase, así que CFR advierte que no pudo cargar otras clases. Es una aproximación, no el código fuente original ni una prueba de que todo el JAR pueda descompilarse correctamente.
- `scripts/decompile-cfr.sh`: ejemplo para descompilar el JAR interno completo en una carpeta local.

## Lo que encontramos

El JAR externo es un **bundle**, no únicamente el servidor. Contiene el JAR interno, 39 bibliotecas y un lanzador. El JAR interno incluye 7 762 archivos `.class`. Las clases inspeccionadas usan nombres legibles, por ejemplo `net.minecraft.server.Main`; no hay archivo de mappings del servidor en los metadatos de esta versión. El formato de bytecode de la muestra es 69 (Java 25).

CFR 0.152 pudo generar una muestra con Java 11, pero es antiguo: la compatibilidad con todos los constructos de Java 25 no está garantizada. Vineflower 1.12.0 requiere Java 17 o superior. El servidor requiere **Java 25**. Inicialmente el entorno solo tenía Java 11; posteriormente se instalaron temporalmente GraalVM 25 y el toolchain Rust y se ejecutaron las pruebas descritas en `mc-aot/README.md`. Esas instalaciones temporales no forman parte del proyecto: instala un JDK 25 y Rust en tu equipo para reproducirlas.

## Descompilar con CFR

Desde esta carpeta, con Java instalado:

```sh
./scripts/decompile-cfr.sh
```

La salida se creará en `analysis/decompiled-cfr/` y puede ocupar bastante espacio. El script apunta al JAR **interno**, no al bundle externo. Si necesitas resolver dependencias al inspeccionar clases, están dentro de `META-INF/libraries/` en el JAR externo; CFR acepta rutas de classpath adicionales. Los descompiladores pueden producir errores o aproximaciones, y no reconstruyen exactamente las fuentes originales.

## Camino hacia JAR → binario

Un descompilador genera Java aproximado, **no Rust ni un ejecutable**. Una ruta experimental más directa es leer el bytecode y compilarlo adelantadamente (AOT), implementando o enlazando el soporte necesario para semántica Java, gestión de memoria, biblioteca estándar, dependencias, reflexión, llamadas nativas y carga dinámica. Una alternativa es un runtime compatible con JVM hecho en Rust, aunque un intérprete no equivale automáticamente a un compilador AOT. El tamaño y complejidad son grandes; no hay garantía de compatibilidad completa ni de mejora de rendimiento. El primer hito razonable es compilar y ejecutar pequeños programas Java de prueba, comparando resultados con una JVM, antes de intentar el servidor.

Minecraft y sus archivos están sujetos a las condiciones de Mojang. Revisa sus términos antes de redistribuir el JAR o código derivado; para ejecutar el servidor debes revisar y aceptar la EULA correspondiente por tu cuenta. No se aceptó ninguna EULA aquí.

## Fuentes

- Manifiesto: https://piston-meta.mojang.com/mc/game/version_manifest_v2.json
- Metadatos 26.3: https://piston-meta.mojang.com/v1/packages/5df1795e16eea19d75b923d66ecca9ce183353c5/26.3.json
- Servidor: https://piston-data.mojang.com/v1/objects/33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c/server.jar
- CFR: https://www.benf.org/other/cfr/
- Vineflower: https://vineflower.org/ y https://repo.maven.apache.org/maven2/org/vineflower/vineflower/1.12.0/

Actualización: la compilación exploratoria de Eula con bibliotecas oficiales alcanza `Comparator.comparing(Function)` en el proveedor Log4j, sin ejecutar Eula ni el servidor. Hay perfiles de reflexión restringidos y guardas que abortan para E/S no implementada; ver `analysis/next-logger-service-loader.md` y `PLAN-ARRANQUE.md`. Rayon continúa como prototipo independiente: no hay todavía binario servidor ni clases completas certificadas.

Tras añadir inicialmente una guarda para `Comparator.comparing` (posteriormente ampliada al perfil de lambda/Integer descrito abajo), el probe exploratorio se detiene al compilar `Collection.stream()` (`analysis/real-eula-comparator-guard-attempt.log`). La guarda no implementa comparadores ni valida el proveedor real.

Actualización: `Collection.stream()` construye ahora un stream perezoso secuencial únicamente para `ArrayList`, inicialmente sin recorrido ni terminales generales; otras fuentes abortan. Se contrastaron 162 resultados de creación/estado/cierre frente a Java (`analysis/arraylist-stream-profile-validation.log`). El probe de Eula con bibliotecas oficiales llega en compilación a `Stream.sorted(Comparator)` (`analysis/real-eula-collection-stream-attempt.log`); no demuestra ejecución del proveedor ni de Eula. Las regresiones integrales `full-regressions-nov.log` y `full-regressions-reflection.log` quedaron interrumpidas al cambiar de sesión; no están aprobadas.

Actualización posterior: `Comparator.comparing` admite `Function` lambda o identidad, y `compare` acepta claves `Integer`, conservando evaluación diferida, orden de llamadas y null; funciones concretas y otras claves abortan. Hay 95 comparaciones Java y guardas (`analysis/comparator-comparing-profile-validation.log`). Esto no implementa el consumo ordenado de `sorted` ni valida el proveedor real.

Actualización posterior: se añadió `ArrayList.stream().max()` secuencial para comparador de claves `Integer`, con 202 resultados frente a Java, incluyendo objetos con prioridades iguales, orden, null y modificación antes del consumo; modificación estructural durante el callback aborta (`analysis/arraylist-stream-max-validation.log`). `Stream.sorted(Comparator)` construye una etapa perezosa, con 82 casos diferenciales; consumir una etapa ordenada aborta explícitamente (`analysis/stream-sorted-profile-validation.log` y `analysis/real-log4j-safestream-sorted-guard.log`). El probe Eula ahora se detiene al compilar `Stream.map(Function)` (`analysis/real-eula-sorted-attempt.log`). Estas operaciones son perfiles restringidos, no streams generales ni validación del logger o servidor.

También se admite construir la etapa `Stream.map` de forma perezosa con Function lambda/identidad; no se admite consumir esa etapa. Se compararon 81 casos con Java y se verificó el aborto en un stream Log4j de fixture (`analysis/stream-map-profile-validation.log`, `analysis/real-log4j-safestream-pipeline-guards.log`). El último bloqueo de compilación del probe Eula es `Collectors.joining` (`analysis/real-eula-map-attempt.log`). No demuestra ejecución de Eula, proveedor de logging ni servidor.

Última actualización: creación `Collectors.joining` con `String`/null (81 casos) y `collect(joining)` sobre ArrayList directo de String/null (162 casos; etapas map/sorted se rechazan); `Optional.orElseGet` (82); hilo principal y flag de interrupción monohilo, incluido `lockInterruptibly` y nombre inicial (142; `setName` no nulo aborta); casts `ConcurrentMap` restringidos (81); y `System.currentTimeMillis` con 162 lecturas Java/nativas dentro de la ventana del reloj del host. Estas pruebas están integradas en `run-regressions.sh`. El probe de Eula con bibliotecas oficiales se detiene al compilar `Properties.entrySet()` en `PropertiesPropertySource` (`analysis/real-eula-thread-name-attempt.log`), sin ejecutar Eula ni el servidor. Rayon sigue desconectado del backend principal.

Último avance: vista `Properties.entrySet()` con iterador solo vacío (81 casos; entradas o modificaciones abortan), `TreeMap.Entry.getKey` (81), adaptación lambda `Class` (81), `Object.equals` para `Class`/`String` (81), inicialización de clases que implementan `CharSequence` (81) e ID del hilo principal con `MC_AOT_JAVA_MAIN_THREAD_ID` explícito (81). Los detalles y guardas están en los tests de `run-regressions.sh`. El último probe de Eula se detiene al compilar `StackWalker.walk(Function)` (`analysis/real-eula-thread-id-attempt.log`); no se ha ejecutado Eula ni el servidor. `Thread.setName` no nulo y las iteraciones no vacías de Properties abortan; el backend sigue siendo monohilo.

La suite integral de esta versión terminó con éxito: 213 etapas en copia aislada (`analysis/full-regressions-startup-corrected.log`), tras corregir una expectativa de guarda en `Object.equals`. No certifica clases completas ni arranque del servidor.

### Avances de arranque: StackWalker y propiedades Log4j

Se amplió el runtime **solo por perfiles**, con pruebas diferenciales frente a Java 25:

- `StackWalker.walk` permite inspeccionar prefijos de frames traducidos con `skip`/`findFirst`, `StackFrame.getDeclaringClass` y `Optional.map`. Hay 73 comparaciones y guardas explícitas para frames externos, callbacks JDK opacos y streams usados fuera de `walk` (`analysis/stackwalker-walk-prefix-validation.log`). Con el bytecode real multi-release de Log4j 2.26.0, `StackLocator.getCallerClass(int)` se contrastó en 91 casos y el frame externo se rechazó; SHA-256 `b0bde864bd4cb3eab35d1530589b25f243307ac1483c15e1fb394a9f993fe917` (`analysis/real-log4j-stacklocator-validation.log`). No es StackWalker general ni ejecuta el logger real.
- Dos patrones exactos de propiedades Log4j admiten `Matcher.find(int)`, `end` y grupo 1 del tokenizer, sobre String/StringBuilder; 1.832 resultados cubren índices, UTF-16 y entrada mutable (`analysis/log4j-property-patterns-validation.log`). Otros patrones, grupos y operaciones se rechazan. `toLowerCase(Locale.ROOT)` solo admite ASCII; Unicode aborta.
- `Set.stream()` crea un stream secuencial perezoso para HashSet, LinkedHashSet y KeySet modelados; `collect` y `max` sobre Set abortan, así como recorridos fuera del perfil. Se contrastaron 81 casos. La inicialización de clases Comparator propias está permitida, pero `Comparator.compare` sobre ellas aborta. `CharSequence.toString` y `Objects.toString(Object,String)` admiten solo String/StringBuilder/null según corresponda.
- Se implementó `REF_invokeSpecial` de lambda únicamente para métodos privados sintéticos de la misma clase con receptor capturado; 162 resultados frente a Java. También `Objects::nonNull` como Predicate (81 casos). `Thread.getContextClassLoader` solo admite el hilo principal y exige `MC_AOT_STANDARD_CONTEXT_LOADER=1`, una afirmación explícita de que su cargador es el sistema estándar; no se modela su cambio ni cargadores personalizados.

La regresión focalizada actual pasó 58+25 pruebas Rust y 19 pruebas diferenciales/perfiles (`analysis/log4j-walk-focused-regressions.log`). El último probe de compilación de Eula con bibliotecas oficiales se detuvo en `Stream.dropWhile` dentro de `StackLocator` (`analysis/real-eula-objects-tostring-attempt.log`); **no ejecutó Eula**. Aunque se ampliaron piezas del logger, las etapas `map`/`sorted` no se consumen de forma general, no se ha validado el proveedor real completo y no se simula un logger. Main sigue bloqueado en ForkJoinPool; Rayon continúa desconectado del backend principal. **No hay servidor nativo ni clases completas certificadas: 0/7.762**. Los resultados diferenciales no equivalen a certificar una clase completa.

La ruta de sink de `Stream.filter` marca callbacks del predicado y consumidor como frames JDK opacos; inspeccionarlos con StackWalker aborta. La prueba con bytecode Log4j y Java real está en `analysis/real-log4j-safestream-callback-stack-guard.log`.

La regresión integral en copia aislada terminó correctamente con 220 etapas (`analysis/full-regressions-log4j-walk.log`), para una revisión anterior a los últimos cambios de Comparator/REF_7/cargador y a la guarda de callbacks del sink. La revisión actual pasó la regresión focalizada indicada arriba y su integral separada en copia aislada terminó con exit 0 y **225 etapas** (`analysis/full-regressions-final-callback.log`). Ninguna certifica clases completas ni el servidor.
