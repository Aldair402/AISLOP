> Estado actual: la última integral aprobada completó **306 etapas** con exit 0 (`analysis/full-regressions-completed-future.log`). Los puentes experimentales no se integran automáticamente en Main: el intento actual sigue bloqueado en `new ForkJoinPool`; **0/7.762 clases completas certificadas, sin servidor nativo**. Los apartados siguientes registran hitos históricos. Los ejecutables de ejemplo están archivados para el snapshot; restauración y regeneración en `analysis/generated-examples-note.md`.

> Futuros: opt-ins `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` y `MC_AOT_RAYON_COMPLETED_FUTURE=1` admiten **solo futuros ya completados normalmente**, no espera/asíncrono ni excepciones. Se contrastaron 90 casos por backend, 20 rondas de captura compartida en Rayon y 80 casos con `ChunkStatusTasks.passThrough` oficial más colaboradores sintéticos; ver `ROADMAP.md` y `analysis/check-*-future-validation.log`. La integral de 306 etapas terminó con exit 0.

# mc-aot: Minecraft JAR → nativo, etapa experimental

> **Roadmap activo:** ver [`ROADMAP.md`](../ROADMAP.md). La integración de log4rs queda aparcada; no se cambia el criterio de no simular logging. Suite integral más reciente: **286 etapas, exit 0**, `analysis/full-regressions-roadmap.log`; no certifica clases.

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

Prototipo en Rust que extrae bytecode de métodos del servidor oficial de Minecraft, genera Rust y lo compila a ejecutables nativos. **Todavía no compila ni ejecuta el servidor completo.** El plan y los obstáculos concretos de la entrada real están en [PLAN-ARRANQUE.md](../PLAN-ARRANQUE.md).

El objetivo es implementar lo que necesite Minecraft, no toda la plataforma Java. Esto no elimina las dependencias que el servidor realmente use: hay que traducirlas o proporcionar equivalentes compatibles.

## Avance actual

**Nota:** las cifras históricas siguientes describen pruebas hechas en distintas etapas; el estado y las restricciones vigentes se mantienen en [PLAN-ARRANQUE.md](../PLAN-ARRANQUE.md). Los métodos sincronizados de instancia, algunos perfiles de archivos y la inicialización predeterminada aislada del proveedor SLF4J se añadieron después de varios de esos experimentos. No implican concurrencia real en el backend ni el arranque del servidor.

- **Objetos y bibliotecas, subconjunto monohilo:** el heap de `multi-static-demo` ahora crea instancias directas de `Object`, ejecuta constructores y métodos concretos, y conserva campos primitivos/referencias, `null` y alias; se contrastaron 238 operaciones con Java, incluida la clase real `FeatureFlagUniverse`. Un test adicional comprobó orden de inicialización, ciclos y constructores encadenados. Admite interfaces inspeccionadas e inicialización JVM restringida, y despacho cerrado de implementaciones directas; **no admite despacho general ni defaults heredados**, herencia general ni sincronización entre hilos; hay excepciones limitadas para subclases directas de `InheritableThreadLocal` y enums finales directos. `volatile` se trata como campo normal únicamente en este modo monohilo: 162 operaciones coincidieron con Java, sin garantías multihilo.
- **Monitores y literales de clase monohilo:** `ldc Class` conserva identidad sin inicializar la clase y `monitorenter`/`monitorexit` mantienen recursión y liberación en este runtime de un hilo. Se compararon 132 operaciones con Java, incluyendo bloques anidados y `finally`. Después se añadieron métodos `synchronized` de instancia en este perfil monohilo; no hay exclusión entre hilos ni métodos estáticos synchronized.
- **Configuración y cadenas restringidas:** `System.getProperty/setProperty/clearProperty` admite perfiles explícitos de claves `slf4j.*`, `log4j*`, `MC_DEBUG_*`, `io.netty.*` y `max.bg.threads`; las demás se rechazan, no se inventan. El valor inicial se configura con `MC_AOT_JAVA_PROPERTIES`, una línea UTF-8 `clave=valor` por propiedad; no equivale a todas las propiedades JVM ni implementa SecurityManager. Una prueba comparó 11 operaciones y cuatro guardas. `String.equalsIgnoreCase` aplica fold Unicode simple generado a partir de Java 25, sin fold expansivo: la tabla contiene 1,483 mapeos, se verificaron 7,505 comparaciones muestreadas (suplementarios y sustitutos aislados incluidos) y 205 ASCII; además, un oráculo Java cotejó los 16,777,216 pares Latin-1 × BMP frente a esa fórmula. No es una validación exhaustiva de todas las cadenas.
- **Logging, enums y arrays de referencia acotados:** `Class.getClassLoader` representa identidad de un único cargador compartido para clases del bundle y `null` para las clases de `java.base` admitidas; no implementa `loadClass`, recursos, reflexión ni `ServiceLoader`. Los literales de interfaz admitidos no inicializan la interfaz. Se añadieron tipos catch reflectivos (ocho comparaciones), sin sus APIs de reflexión. `Object[]`, `Class[]` y arrays de clases finales admitidas tienen covarianza, cast, `aastore` comprobado y clone superficial; 114 operaciones sintéticas coinciden con Java. Se admiten enums finales directos, sin subclases por constante: 92 operaciones sintéticas y otras 92 sobre los enums reales `Reporter$Level` y `Reporter$TargetChoice` de la biblioteca del bundle verificaron inicialización, valores, campos, `name` y `ordinal`. No se certifican clases completas.
- **Más biblioteca de cadenas/salida:** `StringBuilder` limitado a los constructores sin argumentos o con `String`, `append(String/char/int/long/boolean)`, `length` y `toString` pasó 92 operaciones Java, incluidos alias y sustitutos UTF-16. `System.out` y `System.err` tienen identidad separada y `println` acotado (ocho pruebas byte a byte). `String.format` solo admite `%s` con `String` o `null`, `%%` y `%n`: 72 operaciones coinciden; se aborta explícitamente ante otras conversiones, objetos y argumentos ausentes. No reproduce `Formatter`, `Object.toString`, cambios de streams, codificaciones ni errores generales.
- **Biblioteca estándar, equivalentes limitados:** en el mismo modo monohilo se implementaron `ConcurrentHashMap` con claves `String` y valores de referencia no nulos, `LinkedBlockingQueue` no acotada y `ArrayList` para operaciones seleccionadas. Se compararon 300 operaciones de mapa/cola y 300 de lista con Java, además de casos `null` e índices inválidos; las claves no String del mapa se rechazan. La lista permite `null` pero no iteradores ni `equals` arbitrario. También se cubrieron 150 operaciones de `ThreadLocal` exacto y 150 de subclases directas acotadas de `InheritableThreadLocal`, sin hilos. Las subclases que redefinen `initialValue`, `get`, `set` o `remove` se rechazan; no se implementa herencia entre hilos. Se implementó `invokeinterface` **solo** para estas operaciones de colecciones, no despacho general ni semántica concurrente. Las colecciones tienen límites experimentales y no cubren todas las operaciones Java.
- **Pila y objetos reales:** nueve formas de `dup_x1`, `dup_x2`, `dup2_x1`, `dup2_x2` pasaron 36 comparaciones con Java. Mediante un adaptador se compararon 217 operaciones de `SetOnceOptionState`, `CommandResponseTracker` y `SleepStatus` reales, incluidos constructores, mutación, llamadas y estado. Se traducen solo las rutas usadas, no clases completas.
- **Resolución de dependencias:** el lector del bundle busca en los JAR de `versions.list` y luego `libraries.list`, en ese orden, y comprueba el SHA-256 de cada JAR consultado. Una prueba sintética comparó 12 llamadas con Java, verificó precedencia y rechazó rutas inseguras y hashes incorrectos. Esto **no implementa** automáticamente las bibliotecas ni verifica los JAR que no se consultan.
- **Preparación de flotantes:** campos estáticos `float`/`double` se preparan conservando los bits de sus valores por defecto o `ConstantValue`; `@campo` imprime `fbits:`/`dbits:` y los bits hexadecimales. Se compararon 14 campos sintéticos y 97 campos reales de 33 clases sin `<clinit>` frente a Java. **El bytecode de acceso y la aritmética float/double siguen sin soporte y se rechazan.**
- **Campos estáticos de referencia restringidos:** `multi-static-demo` admite campos `String`, `String[]` y arrays primitivos, con `null`, alias entre clases e internado de `ConstantValue` String antes de `<clinit>`. Se contrastaron 212 operaciones sintéticas, otras 225 para los seis tipos de arrays primitivos y una inicialización circular con literal UTF-16 que incluye un sustituto aislado. En código real se compararon el array hexadecimal de `PktUtils` y la inicialización y reasignación de arrays de `FoliageColor` y `DryFoliageColor` frente a Java 25. Una auditoría de 99 clases por forma generó 92 programas que leen un campo; sus 92 lecturas coincidieron por muestreo, incluidas 18 `String` y cuatro programas con `<clinit>`. No se han traducido clases completas.
- **Inicialización multiclase acotada:** `multi-static-demo` prepara campos primitivos de varias clases y ejecuta `<clinit>` al primer uso, con estado compartido y manejo monohilo de ciclos de inicialización. En tres clases sintéticas se contrastaron 256 operaciones con Java 25, incluidos un ciclo, orden, preparación y estado persistente. Se compararon también 116 lecturas de `BiomeManager` con su llamada a `QuartPos` y 284 lecturas de 71 programas de una auditoría más amplia; solo uno de esos programas ejecuta un `<clinit>` real. Se rechazaron siete formas no soportadas. **No son clases completas**. El modo acepta clases directas de `Object`, subclases acotadas de `InheritableThreadLocal` o enums finales directos, interfaces inspeccionadas y por defecto como máximo 256 clases (configurable mediante `MC_AOT_MAX_STATIC_CLASSES`, entre 1 y 4.096). Soporta handlers y los fallos monohilo de inicialización del subconjunto: en diez operaciones coincidieron con Java el primer `ExceptionInInitializerError`, posteriores `NoClassDefFoundError`, propagación de `Error` con identidad, fallos anidados y excepciones capturadas. No implementa causas, mensajes, stack traces ni concurrencia.
- **Tipos de excepción Minecraft:** se resuelven las cadenas de superclases `net/minecraft/` para `catch`. La construcción se limita a excepciones sin campos ni `<clinit>`, con constructores comprobados que delegan trivialmente en su supertipo. Con `NbtException` real, una subclase sintética y relanzamientos se contrastaron 26 casos frente a Java; se rechazaron tres clases o constructores no triviales. Se resuelve el tipo `ReportedNbtException` como `catch`, **pero no se implementa su constructor ni sus campos**. No se certifican clases completas ni se implementan sus mensajes, causas o stack traces.
- **Excepciones acotadas:** la ruta numérica lee y valida tablas de manejadores y selecciona el primero que corresponde al offset y tipo; propaga excepciones entre llamadas, permite `athrow`, `finally` y conserva la identidad al relanzar. Admite excepciones incorporadas y tipos Minecraft cuya jerarquía puede resolver, incluyendo `ArithmeticException`, `NullPointerException`, errores de índice, `ClassCastException`, `ArrayStoreException`, `IllegalArgumentException`, `NumberFormatException`, `IOException` y sus supertipos admitidos. Puede construir esas excepciones con `()` o `(String)`, pero **no implementa `getMessage`, causas ni stack traces**, y admitir `IOException` no implementa el sistema de archivos. En 106 casos sintéticos coincidieron con Java valores o categorías, incluyendo jerarquía, orden, propagación, `finally`, creación y relanzamiento; se rechazaron cuatro tablas malformadas y un tipo catch desconocido. Una prueba adicional comprobó una excepción capturada en `<clinit>` y nueve operaciones con estado. El método real `LayerLightSectionStorage$SectionState.neighborCount(byte,int)` construye y lanza `IllegalArgumentException`: se compararon 2,048 combinaciones con Java 25 en valor o categoría del error, no mensaje ni stack trace. El transporte usa desenrollado de panic Rust dentro del proceso nativo, con `panic=unwind`; no es el mecanismo ni el rendimiento de una JVM. Una excepción no capturada termina el proceso con código 2. Las rutas antiguas de objetos y primitivas no tienen este modelo; el compilador deriva al backend numérico cuando corresponde.
- **Cadenas y punto de entrada acotado:** la ruta numérica representa `String` en unidades UTF-16, conserva identidad e interna literales; admite `String[]`, `aaload`/`aastore`, creación, `null`, `checkcast` restringido y algunas operaciones de `String` y `System.out.println`. Un `main(String[])` sintético se tradujo y sus seis ejecuciones coincidieron byte a byte con Java 25, incluidos argumentos Unicode, pares sustitutos, literal con sustituto aislado, arrays y salida. Otras 3,567 comparaciones cubrieron cuatro métodos reales (`Identifier.isValidPath/isValidNamespace` y `ShapedRecipePattern.firstNonEmpty/lastNonEmpty`) y diez sintéticos, además de cinco comprobaciones de `String[]`, cuatro rechazos y nueve pruebas de `checkcast`/orden de errores de `aastore` frente a Java. En Java se ejecutó el bootstrap de registros para cargar `ShapedRecipePattern`; el programa nativo no lo ejecuta. En esas pruebas, los fallos sin manejador se contrastaron por categoría y terminaron el proceso. La prueba es por muestras, no certifica clases ni comportamiento general de Java. Informes: `analysis/string-main-comparison.log`, `analysis/string-comparison.log`.
- **Inicialización estática restringida:** `static-demo` prepara campos estáticos `int`, `long` y primitivos pequeños, respeta sus atributos `ConstantValue` y ejecuta `<clinit>` una sola vez antes de la primera operación. Permite leer campos por nombre y llamar varios métodos seleccionados en una misma ejecución, conservando estado. Se contrastaron 355 operaciones en una clase artificial, seis constantes y 116 lecturas de cuatro campos reales de `BiomeManager`, incluido su `<clinit>` y la llamada a `QuartPos.fromBlock`. Una auditoría de forma compiló 14 programas y los 14 se compararon con Java en 56 lecturas de un campo por clase. **No son clases completas.**
- **Arrays primitivos:** la ruta numérica acepta argumentos unidimensionales `boolean[]`, `byte[]`, `char[]`, `short[]`, `int[]` y `long[]`, además de crear arrays locales y leer/escribir sus elementos. Mantiene identidad de referencias y alias entre llamadas; admite `null`, longitud y controles de límites. Se compararon 1,535 resultados de 10 métodos reales y 13 sintéticos con Java 25, y otras 336 muestras de 14 de los 15 métodos que compilaron en el barrido del JAR. El restante, `MapItem.isBiomeWatery`, se comparó por separado en 83 casos después de ejecutar el bootstrap de registros **en Java**, sin iniciar el servidor; el binario nativo no implementa ese bootstrap. `NullPointerException`, `ArrayIndexOutOfBoundsException` y `NegativeArraySizeException` se contrastaron por categoría en esas pruebas, sin manejadores. El heap experimental no tiene GC y limita cada ejecución a 10,000 objetos/arrays y 1,000,000 elementos o unidades UTF-16 acumulados; superar el límite termina con un error propio, que no equivale a una excepción Java.
- **Enteros `long` y coordenadas:** la ruta numérica admite firmas estáticas con `int`, `long` y los tipos primitivos pequeños, mezclados en argumentos y retorno. Usa una pila que distingue valores de categoría 1 y 2 y respeta los dos slots locales de `long`; incluye operaciones de 64 bits, conversiones, comparaciones, desplazamientos, llamadas estáticas compatibles y `wide` numérico. Las rutas anteriores siguen siendo la primera opción para firmas con solo primitivas pequeñas; si fallan, se intenta la ruta numérica. Las firmas con `long` o arrays van directamente a ella. `compile-numeric` permite seleccionarla directamente. Se compararon 2,622 resultados de 12 métodos reales y 17 métodos sintéticos con Java 25, además de 960 muestras de los 40 métodos `long` compilables de la auditoría. Las pruebas de `wide` y de las formas de pila sumaron 28 comparaciones adicionales; se comprobaron cinco rechazos de funciones no implementadas. Son muestras, no pruebas de equivalencia completa; las excepciones aritméticas se comparan solo por categoría.
- **Más instrucciones y tipos primitivos:** la ruta de flujo baja `tableswitch`, `lookupswitch` y `goto_w` a una máquina de estados. `PngInfo.validateBitDepth` y `validateColorType` y tres métodos sintéticos produjeron 760 resultados coincidentes con Java 25. Los argumentos `boolean`, `byte`, `char` y `short` también están admitidos además de `int`: cinco métodos reales y una llamada sintética produjeron 827 coincidencias; se rechazaron ocho valores fuera del rango de la firma. Las entradas CLI de `boolean` son 0 o 1; las demás deben estar en el rango del tipo Java.
- **Campos de referencia:** `reference-demo` traduce un constructor y un getter de `String` de una clase concreta. Se comprobó la identidad del campo de `FeatureFlagUniverse`, incluidos `null` y cadenas distintas con el mismo contenido. Un barrido comparó seis pares reales constructor/getter con Java 25. Es una representación limitada, no una implementación general de `java.lang.String`.
- **Heap mixto:** `multi-demo` puede incorporar explícitamente una de esas clases mediante `--reference`. Los objetos de altura y el campo de referencia comparten el mismo vector de objetos. Se compararon 201 secuencias mixtas y tres casos de `null` contra Java 25; el error nativo termina el proceso, no es una excepción Java capturable.
- **Referencias y despacho experimental:** `multi-demo` genera un programa que aloja múltiples instancias de dos clases concretas, copia referencias, compara identidad, representa `null` y elige el método según la clase de cada objeto. Se probó con `LevelHeightAccessor$1` y `BelowZeroRetrogen$1` del JAR real; no es un runtime JVM general.
- **Primera prueba con instancias y campos:** `object-demo` traduce el constructor y los dos getters declarados de `LevelHeightAccessor$1`, incluida la lectura/escritura de sus campos `int`. También puede incorporar explícitamente `getMaxY`, un método default de su interfaz, con las dos llamadas de interfaz resueltas para esa clase concreta. No es despacho virtual general ni un heap Java.
- Se compararon 155 objetos y 620 llamadas a esos métodos con Java 25; además, una clase artificial pasó 535 llamadas de prueba y se comprobaron siete rechazos de características no soportadas. Para el nuevo runtime se compararon 202 secuencias con Java usando las dos clases reales y 104 secuencias sintéticas que verifican que una mutación mediante un alias se observa mediante el otro. Para `null` se comparó la categoría del fallo: el programa Rust termina, en vez de lanzar una excepción Java capturable. No se han validado los demás métodos heredados ni las clases completas.
- Se combinan **saltos y llamadas** en un mismo método, mediante una máquina de estados Rust. Se han traducido, entre otros, `LightCoordsUtil.lightCoordsWithEmission` y `smoothBlend`, que llaman otros métodos de esa clase.
- Se resuelven **llamadas estáticas entre clases de Minecraft** dentro del subconjunto admitido. Ejemplo: `FillBiomeCommand.quantize` llama a `QuartPos.fromBlock` y `toBlock`; `Goal.reducedTickDelay` llama a `Mth.positiveCeilDiv`.
- La ruta lineal genera expresiones Rust; la de saltos genera una máquina de estados. No se ha medido su rendimiento.
- Se añadieron división y resto enteros, conversiones `i2b/i2c/i2s`, operaciones de pila y retornos boolean/byte/char/short; los resultados se representan como `i32` en el ejecutable. También hay equivalentes de `Math.floorDiv/floorMod/abs/min/max` para enteros.

Se han generado binarios para **55 métodos reales** de Minecraft 26.3. De ellos, los 20 originales produjeron **2,720 resultados** coincidentes con Java 25, en 136 conjuntos de entradas, incluidos límites, valores aleatorios y divisiones por cero. Las nuevas comparaciones de switches y tipos de argumento se describen arriba. Los errores aritméticos se compararon por categoría: el programa nativo termina con código 2, mientras Java lanza una excepción. No es equivalencia completa de excepciones ni una prueba exhaustiva.

Pasaron 27 pruebas unitarias. Otra prueba usa una clase Java artificial para comprobar 630 resultados (incluidas conversiones y errores aritméticos) y confirmar que se rechazan recursión, objetos y métodos `synchronized` no implementados. La prueba con código real está en `../graal-test/compare-mth.py`; la prueba artificial, en `tests/check-guards.py`.

Ejemplos:

```text
wrapDegrees(270)       → -90
roundToward(17, 8)     → 24
quantize(-9)           → -12
positiveModulo(-7, 3)  → 2
```

Los ejemplos en `examples/` son ELF dinámicos para **Linux x86-64**; usan bibliotecas del sistema, pero no necesitan Java ni el JAR al ejecutarse. Los `.rs` junto a ellos son el Rust generado.

### Ruta concurrente experimental

`concurrent-int-demo` traduce un subconjunto de métodos estáticos enteros a frames Rust, con cuatro trabajadores, métodos synchronized reentrantes, objetos de clases final sin jerarquía con campos int, y heap de campos `static volatile` o `static final` enteros o referencias a esos objetos compartido. Por ejemplo:

```sh
cargo run --manifest-path mc-aot/Cargo.toml -- concurrent-int-demo downloads/server-26.3.jar net/minecraft/core/QuartPos /tmp/quart quartLocal '(I)I'
/tmp/quart -7 0 11
```

Para la ruta de proveedores de Log4j se añadieron perfiles monohilo restringidos: `Iterable.iterator` para `ServiceLoader` y colecciones ya admitidas (102 comparaciones de iterador de ArrayList); subclases **finales directas** de `AbstractSpliterator` sin overrides de sus operaciones base, con tamaño y características (103 casos); y construcción perezosa de `StreamSupport.stream` secuencial, `filter` con predicados lambda, `isParallel` y `close` (86 casos); el filtro guarda la cadena pero no consume elementos ni invoca callbacks. `trySplit`, streams paralelos y predicados que no sean lambdas no están implementados. `forEach` solo admite el `ServiceLoaderSpliterator` oficial de Log4j 2.26.0 con SHA-256 exacto, propagando filtros y excepciones dentro de su `tryAdvance`; otras fuentes abortan y se limita a 1.000.000 de avances. El fixture `check-real-log4j-safestream.py` contrastó 201 resultados del método y spliterator oficiales con proveedores y logger **sintéticos**, no el logger real. `StackWalker.getInstance()` por defecto conserva identidad y rechaza `getCallerClass` sin `RETAIN_CLASS_REFERENCE`; 180 casos lo contrastaron con Java.

La opción de traducción **`MC_AOT_CLOSED_CLASSPATH=1`** permite únicamente `Class.forName("org.osgi.framework.FrameworkUtil")` cuando el índice del JAR/bundle demuestra que esa clase no está presente: lanza `ClassNotFoundException`, igual que Java en ese classpath cerrado. El opt-in declara que no se añadirán clases por agentes ni cargadores externos; otros nombres abortan y si la clase sí está en el bundle se rechaza la traducción. Se contrastaron 41 casos y las guardas (`tests/check-class-forname-osgi.py`). No implementa `Class.forName` general ni OSGi.

La compilación de la rama OSGi de `ServiceLoaderUtil.safeStream` solo se evita con `MC_AOT_CLOSED_CLASSPATH=1`, ausencia comprobada de FrameworkUtil y hashes exactos de `ServiceLoaderUtil` y `OsgiServiceLocator`. La llamada real a `isAvailable` y su inicialización se conservan; si se ejecuta una de las dos instrucciones OSGi omitidas, el binario aborta. Se comprobaron también las guardas de hashes y de presencia.

Otras piezas contrastadas son `RuntimePermission(String)` como datos, sin políticas; despacho de `BooleanSupplier` y `PrivilegedAction.run`, no `doPrivileged`; `ClassLoader[]` y su cast solo con el cargador de aplicación; `WeakReference` solo para ese cargador arraigado o null; `LinkedHashSet(int)` para String/null; y `ConcurrentHashMap.newKeySet()` monohilo solo para String/Class, sin iteración ni objetos arbitrarios. `Set::add` admite la referencia de método con resultado descartado por Consumer o conservado por Predicate. `MC_AOT_STANDARD_SYSTEM_LOADER=1` es un opt-in adicional que declara un system loader estándar, sin personalización; entonces `getSystemClassLoader` devuelve el mismo handle de aplicación. El recurso `META-INF/log4j-provider.properties` solo se enumera como ausente tras comprobar el bundle bajo classpath cerrado. `URL.openStream` no está implementado: solo respeta receptor null y aborta si se alcanza una URL. El patrón literal de duración Log4j y flags 2 se construye, pero `matcher` no está soportado.

`HashSet` acepta también claves `Class` dentro del modelo de un único cargador, junto con `String` y `null`; la igualdad de clases usa identidad. Un fixture contrastó 81 secuencias con Java, incluida la inserción a través de `Collection` de `objeto.getClass()`, patrón usado para deduplicar proveedores de Log4j (`tests/check-hashset-class-keys.py`, `analysis/hashset-class-regressions.log`). La iteración de más de un elemento sigue abortando por orden no verificado, y los objetos arbitrarios siguen rechazándose. La ruta restringida de `safeStream` se cotejó por separado con las limitaciones indicadas arriba.

Una prueba adicional reúne en un solo ejecutable `multi-static-demo` los cinco métodos estáticos declarados y los cuatro campos constantes de `QuartPos` oficial: **2.579 resultados** coinciden con Java, incluidos límites y 500 enteros aleatorios (`tests/check-quartpos-class-surface.py`, `analysis/quartpos-static-surface.log`). No prueba el constructor privado ni la reflexión general; no se contabiliza como clase completa.

La ruta no es `Thread` ni `ForkJoinPool` de Java: admite firmas internas `(I)I`, `()I`, `(I)V` y `()V`, clases sin interfaces ni superclases propias, y solo ciertas instrucciones. El `<clinit>` acotado de la clase raíz se ejecuta una vez antes de los trabajos; las clases de objetos no admiten inicializador. Los argumentos enteros forman un lote y `--phase` separa lotes con una barrera. Rechaza lo demás; tiene límite de pasos, no GC ni excepciones Java generales. Tres métodos reales de `QuartPos` produjeron 615 resultados coincidentes con Java, sin certificar la clase completa.

### Adaptador Rayon de ForkJoin (experimental)

`concurrent-rayon-int-demo` usa Rayon 1.11.0 con el `Cargo.lock` del proyecto para compilar un ejecutable independiente, sin JVM externa. Necesita `cargo`, `rustc` y acceso a las dependencias al menos una vez (o caché local). El directorio de compilación temporal se puede elegir con `MC_AOT_RAYON_TARGET_DIR`. Ejemplo:

```sh
cargo run --manifest-path mc-aot/Cargo.toml -- concurrent-rayon-int-demo downloads/server-26.3.jar net/minecraft/core/QuartPos /tmp/quart-rayon quartLocal '(I)I'
/tmp/quart-rayon -7 0 11
```

Esta ruta **separada del backend principal** admite un perfil acotado del bytecode de `ForkJoinPool`: constructor `(I)V` con paralelismo 1–255 y constructor de cuatro argumentos con factory predeterminada y handler null, `submit(Runnable)`, `execute(Runnable)` directo o por interfaces `Executor`/`ExecutorService`, `ForkJoinTask.join()` y `shutdown()`. La tarea debe ser una clase `final` directa de `Object`, que implemente solo `Runnable`, con campos de instancia `int`, `AtomicInteger` o `String` dentro del perfil y método `run()V` traducible. Los `join` repetidos y anidados pueden ayudar a ejecutar tareas del mismo pool. También permite llamadas a métodos estáticos enteros de otras clases Minecraft directas de `Object` sin inicializador, mientras el método cumpla el perfil. El adaptador se basa en work stealing de Rayon; no promete el mismo orden de ejecución. El pool de Rayon se crea al primer envío, pero entonces crea todos sus trabajadores, mientras que Java puede crearlos gradualmente.

`tests/check-rayon-java-forkjoin.py` contrasta 78 resultados y 279 tareas ejecutadas desde bytecode Java que invocan `QuartPos.toBlock` oficial, incluidos joins anidados en un pool de un hilo. `tests/check-rayon-forkjoin-profile.py` compara 4.000 trabajos y otras propiedades acotadas con un ForkJoinPool Java real. Las pruebas no certifican la clase Minecraft ni el servidor.

El constructor de cuatro argumentos admite **factories Java restringidas** (`async=true`, paralelismo 1, handler null): clases finales con patrones exactos y lambdas de `LambdaMetafactory` con capturas `String` y `AtomicInteger` en ambos órdenes. Se valida el bytecode de la factory, la concatenación de nombre y el constructor del worker, que debe ser subclase final directa de `ForkJoinWorkerThread`, sin overrides de `run`/`start`, y con hasta dos campos finales `String`. Se traducen `newThread`, `onStart` y `onTermination` para terminación normal; una falla no se convierte en excepción Java. En los patrones validados de factory se admite `setName`, y `getName` solo con nombre previamente establecido. El nombre también se entrega al hilo Rust; se rechazan NUL y UTF-16 no representable, el nombre predeterminado y renombrados fuera de la factory.

`tests/check-rayon-java-worker-lifecycle.py` comparó **312 resultados** con Java, incluyendo hooks, `QuartPos.toBlock` oficial, esperas, comparaciones de identidad y ramas `ifnull`/`ifnonnull`, `long`, 4.800 incrementos `AtomicInteger`, concatenación UTF-16 y guardas. Una lambda sintética y un constructor de dos cadenas usan la misma secuencia de instrucciones y locales que `Util.lambda$makeExecutor$0` y el constructor de `Util$2` oficiales (ignorando índices del pool de constantes); el test comprueba esa coincidencia automáticamente. Para el fixture se añadió `ACC_FINAL` a la clase anónima sintética y tanto Java como el AOT usan esa misma clase modificada. **No son las clases oficiales**: el `Util$2` real no es final. El compilador permite ahora únicamente sus bytes oficiales con SHA-256 `0324db47427384d1dfe3e0e9f61410121af90931d9267f08ec85bc6f164cb205`: un llamador artificial alcanza el registro por patrón del constructor, pero la compilación se detiene en `Util.LOGGER`, aún no soportado. El probe comprueba también el rechazo sin opt-in de Tracy y de una clase modificada (`tests/check-real-util-worker-guards.py`); no ejecuta el ciclo de vida completo ni produce un binario de ese llamador. Un segundo probe traduce y ejecuta por separado **el constructor y `onStart` oficiales** de `Util$2`, invocados directamente desde un llamador artificial con Tracy sin cargar: 12 resultados concuerdan con Java, con cadenas Unicode y null (`tests/check-real-util-worker-onstart.py`, `analysis/real-util-worker-onstart.log`). Esta prueba no inicia ese objeto como worker ni valida los efectos internos completos del constructor de `ForkJoinWorkerThread`; tampoco prueba `onTermination`, el logger ni la lambda real.

Se puede ejecutar el bytecode **oficial** de `TracingExecutor.shutdownAndAwait(long, TimeUnit)` en una ruta delimitada: `MC_AOT_RAYON_ASSUME_NO_INTERRUPT=1` al traducir, SHA-256 exacto de `TracingExecutor.class` `80786a96dc2259a9c16eeb9c3329400c830c02cc568069581eee4789e62b5e32`, campo `ExecutorService` que contiene un ForkJoinPool del perfil, cierre exitoso dentro del timeout y ninguna interrupción Java. El catch de `InterruptedException` no se implementa: esa bandera declara la suposición y se rechaza la traducción sin ella o con otra versión de clase. Si termina el plazo y se alcanza `shutdownNow`, el ejecutable falla explícitamente; no pretende cancelación equivalente. `tests/check-real-tracing-shutdown.py` contrastó 12 resultados, usando también `QuartPos` oficial, y verifica las tres guardas. Además, el mismo fixture ejercita el bytecode oficial de `TracingExecutor.execute` y `wrapUnnamed`: requiere también `MC_AOT_RAYON_ASSUME_NO_TRACY=1` al traducir y verifica el SHA-256 `55d6a5576bd91504ebdea28af611a243aa5e0b1f288d78241f788e34c0c2f3a1` de `TracyClient.class` oficial. Bajo esa suposición explícita, `isAvailable` se especializa a false y la rama de Tracy activo aborta si se alcanza; no implementa ni simula Tracy activo. El mismo perfil admite el accessor oficial `service()` cuando su valor es un pool soportado. La llamada por la interfaz `Executor` también despacha al `execute` traducido de clases finales registradas, incluido `TracingExecutor`. El diferencial suma 48 resultados entre cuatro rutas y comprueba además las guardas de opción y hash de Tracy. Son rutas de métodos, no la clase completa ni el servidor. El mismo opt-in sin Tracy y el mismo SHA permiten `TracyClient.setThreadName(String,int)` solo con la suposición de que Tracy no se carga: en esa rama el método oficial retorna sin llamar a código nativo. Se contrastaron **24 resultados**, incluidos nombre nulo y llamada desde un callback sintético, además de las guardas de opción y hash (`tests/check-real-tracy-thread-name.py`, `analysis/real-tracy-thread-name.log`). No se implementa la activación de Tracy ni se certifica la inicialización completa de esa biblioteca.

En el heap concurrente, los literales `String` se internan por unidades UTF-16 bajo mutex; `length()` y `hashCode()` se contrastan con Java incluso con NUL y sustitutos aislados. Se admiten campos `String` acotados; Se admite también `StringConcatFactory.makeConcatWithConstants` exclusivamente para `(String,int)String`, receta con dos argumentos y sin constantes adicionales; maneja `null`, extremos `int` y UTF-16 y crea un objeto nuevo. El resto de concatenaciones, `equals`, constructores y API de cadenas se rechaza.

El backend Rayon también admite un `AtomicInteger` compartido muy limitado: constructor `(int)`, `get()` y `getAndIncrement()`. La lectura-modificación-escritura usa el mismo mutex del heap compartido y el desbordamiento es de 32 bits. El fixture diferencial ejecuta 4.800 incrementos en pools de cuatro trabajadores y prueba el valor anterior y los extremos; una prueba Rust verifica 4.000 valores anteriores distintos bajo contención. Otros métodos y clases atómicas se rechazan: esto no certifica la clase Java completa.

**Todavía no es el ForkJoinPool que necesita el arranque real.** Minecraft usa un constructor con factory y handler Java propios; `Util$2` incluye callbacks de Tracy y registro de terminación. El ciclo de vida completo del worker oficial, factories generales, handlers, implementaciones arbitrarias de `ExecutorService`, interrupción, cancelación, `shutdownNow` y excepciones Java de tareas no están implementados. `awaitTermination` directo o por `ExecutorService` solo está soportado para pools de este perfil, los siete `TimeUnit` y valores `long` acotados al subconjunto de bytecode implementado; se esperan las tareas y los callbacks de terminación, no se implementa `InterruptedException` y la autoespera desde un trabajador o sus callbacks se rechaza. Las esperas que agotan tiempo y la conversión saturada se contrastaron con Java; las carreras, callbacks fallidos y autoesperas se prueban en `tests/rayon_await.rs`. La espera interna `await_closed_idle` solo detecta que cerró el pool y terminaron sus trabajos; no equivale a la terminación de los hilos Java. Si falla una tarea `execute`, el proceso aborta con un diagnóstico: no implementa el handler Java. El ejecutable aborta ante operaciones que el perfil no soporta, en lugar de simularlas. El backend `multi-static-demo` sigue siendo monohilo y no comparte su heap con Rayon. Inventario de referencias directas: `analysis/forkjoin-direct-calls.tsv` (no incluye usos por interfaz ni reflexión).

Para repetir la suite completa de pruebas, comparaciones y auditorías (puede tardar varios minutos):

```sh
JAVA_HOME=/ruta/a/jdk-25 ./run-regressions.sh
```

Los informes se escriben en `../analysis/`. No certifica clases completas ni arranque.

## Requisitos

- `cargo`, `rustc`, `unzip`, `sha256sum` y `gzip` en `PATH`. El proyecto depende de Rayon 1.11.0 y sus dependencias bloqueadas en `Cargo.lock`; Cargo debe poder acceder a ellas o tenerlas en caché.
- Para las comparaciones, Python 3 y un JDK 25 con `java`, `javac` y `jar`.
- El Rust y GraalVM usados para las pruebas se instalaron temporalmente y no forman parte de esta carpeta. En otros sistemas recompila los ejemplos; en Windows también deberás adaptar rutas y disponer de `unzip`.

## Inicialización estática: experimento de una clase

`static-demo` es una vía separada del compilador normal. Solo admite una clase que herede directamente de `Object`, sin interfaces, con campos estáticos exclusivamente `I/J/Z/B/C/S` no `volatile`. Rechaza lecturas/escrituras de campos de otras clases. Puede llamar métodos de la misma clase o una clase auxiliar de Minecraft que pase un filtro estricto: herencia directa de `Object`, sin interfaces ni `<clinit>` y sin campos estáticos de referencia o `volatile`; no se admiten accesos a sus campos. `Math` solo se admite mediante los intrínsecos existentes. No representa inicialización de jerarquías arbitrarias, concurrencia, sincronización, fallos de inicialización capturables ni el ciclo de vida completo de clases JVM. Un `<clinit>` puede capturar las excepciones del subconjunto mientras se ejecuta. Una falla de `<clinit>` termina el proceso y no reproduce `ExceptionInInitializerError` / `NoClassDefFoundError`.

El comando selecciona pares `<método> <descriptor>` y lecturas `<@campo> <descriptor de campo>`; al ejecutar, cada operación se identifica con su índice, empezando en cero, seguido de sus argumentos. Cada método `void` imprime `OK`. El acceso `@campo` es una ayuda de inspección que también puede leer campos privados, no reproduce las reglas de acceso Java.

```sh
cargo run -- static-demo ../downloads/server-26.3.jar net/minecraft/world/level/biome/BiomeManager ./biome-init '@CHUNK_CENTER_QUART' I '@ZOOM_BITS' I '@ZOOM' I '@ZOOM_MASK' I
./biome-init 0 1 2 3
# 2, 2, 4, 3 (uno por línea)
```

El `<clinit>` de `BiomeManager` llama a `QuartPos.fromBlock` para obtener el primer campo; los demás se preparan a partir de `ConstantValue`. El ejemplo no ejecuta el resto de métodos ni las clases completas. Fuera de `static-demo` y `multi-static-demo`, `compile` y `compile-numeric` **siguen sin ejecutar inicializadores**.

## Aislar los archivos de rendimiento de Java en las pruebas

En un entorno con `/tmp` compartido, dos JVM pueden intentar usar el mismo fichero `hsperfdata` y una advertencia puede contaminar el stdout del oráculo. Se puede crear un `JAVA_HOME` temporal que ejecuta el mismo JDK con `-XX:-UsePerfData`, sin imprimir opciones adicionales en stderr:

```sh
JAVA_HOME=$(bash mc-aot/tools/java-no-perf-wrapper.sh /ruta/al/jdk-25 /var/tmp/jdk-sin-perf)
export JAVA_HOME
bash mc-aot/run-regressions.sh
```

La ruta de salida debe ser nueva; el wrapper y el JDK temporal no se guardan en el workspace. Esta opción solo desactiva los contadores de rendimiento de la JVM del oráculo, no la usa el binario nativo.

## Puente de prueba entre los dos heaps

Un adaptador interno `numeric_concurrent_bridge.inc` permite que `SharedHeap` apunte al almacenamiento y monitor de un objeto del heap numérico, sin copiar campos. Solo admite campos Java `int`; el harness debe validar previamente el layout por classfile porque `V::I` también representa tipos estrechos. `SharedHeap` conserva identidad local, rechaza IDs ajenos y no retiene su mutex al invocar el adaptador o esperar el monitor; operaciones CAS/RMW externas se rechazan.

`tests/check-numeric-concurrent-bridge.py` une explícitamente dos fuentes Rust generadas y suministra la publicación y layout: el backend principal ejecuta métodos Java traducidos y el concurrente traduce el bytecode Java de un `ForkJoinPool` con cuatro `Runnable`, `submit`, `join` y `shutdown`, todos sobre el mismo objeto y monitor. Son 20 rondas contrastadas contra Java 25, con bytecode `QuartPos.toBlock` oficial, overflow, guardas y ejecución del test nativo sin Java en PATH. No se producen excepciones Java equivalentes desde fallos internos.

Un segundo experimento, `numeric_concurrent_graph_bridge.inc`, añade lectura de referencias finales entre objetos previamente registrados en una sesión ligada al heap numérico. El test `check-numeric-concurrent-graph.py` verifica el layout contra el classfile, y la tarea Java traducida atraviesa `root.next` hasta un segundo objeto bajo el monitor compartido. Se compararon 20 rondas por variante con Java 25; la segunda materializa y ejecuta `TickTask.run/getTick` oficial, sin afirmar que el servidor lo envíe al pool. Solo tipos exactos, referencias de lectura y objetos registrados; no subtipos, escritura de referencias, arrays o String. IDs ajenos y sesiones cerradas se rechazan.

Es una **prueba opt-in**, no una opción automática del traductor: no conecta `Main`, no comparte estáticos ni referencias de campos de forma general, y no implementa inicialización concurrente, interrupciones, wait/notify o ciclo de vida completo de `ForkJoinPool`. No hay clases completas certificadas. Ver `analysis/numeric-concurrent-bridge-validation.log` y `analysis/next-numeric-concurrency-integration.md`.

## Capturas de objetos en el backend concurrente

Con `MC_AOT_RAYON_PROJECT_REFERENCES=1` al compilar `concurrent-rayon-int-demo`, un `Runnable` final puede capturar mediante un campo **final** un objeto final de proyecto sin interfaces, jerarquía ni `<clinit>`, de tipo declarado exacto. Los objetos se materializan en `SharedHeap`, no en el heap numérico principal; las escrituras de referencia quedan restringidas al constructor y se comprueba el tipo exacto. Referencias de otro tipo, campos mutables, clases abiertas y perfiles fuera de las guardas se rechazan. La bandera también habilita `TickTask` oficial no final únicamente si su SHA-256 coincide: materializa el objeto y ejecuta `run()` y `getTick()` traducidos, incluido el `Runnable.run` capturado conocido. No se admite despacho de subclases. El resto del perfil concurrente sigue limitado; no hay excepciones Java generales, interrupciones, GC ni colas de ticks completas.

Por ejemplo, con el JAR del fixture y sus clases ya preparado:

```sh
MC_AOT_RAYON_PROJECT_REFERENCES=1 cargo run --manifest-path mc-aot/Cargo.toml -- \
  concurrent-rayon-int-demo fixture.jar net/minecraft/test/CapturedFixture ./capturas run '(I)I'
./capturas 1000
```

En `tests/check-rayon-java-captured-object.py` y `tests/check-rayon-real-ticktask-capture.py` cuatro tareas y la invocación principal comparten un `Cell` y su monitor; el bytecode del fixture construye el `ForkJoinPool`, ejecuta `submit`, `join` y `shutdown`, y el de `TickTask` y `QuartPos` es oficial. Hay 28 comparaciones por prueba contra Java 25, overflow y guardas; el binario se ejecutó sin Java en el PATH. Se usa el adaptador Rayon del backend concurrente, **no** el backend principal ni `Main`, y no se implementa toda la semántica de `ForkJoinPool` ni se certifica `TickTask` como clase completa.

## Tarea Java sobre el heap numérico: perfil experimental

El comando `shared-worker-demo` compila un perfil deliberadamente estrecho de `Runnable.run()` a código Rust y ejecuta cuatro tareas en Rayon sobre el **mismo objeto y monitor** utilizados por métodos Java traducidos con `multi-static-demo`. Valida las clases, flags, capturas, constructores, referencias y bytecode exacto antes de compilar: tarea `final` con una captura final; objeto destino `final` con un único `int` mutable no `volatile`; `run()` llama a un método de instancia `synchronized` cuyo único efecto es incrementar ese campo. Se admite el incremento por 1 o por el resultado de `QuartPos.toBlock(1)` solo cuando el bytecode de `toBlock` es exactamente el verificado y no tiene inicializador de clase. Los métodos raíz `tick` y lectura también se restringen a formas exactas. Tareas y métodos fuera del perfil se rechazan, al igual que la captura nula. El objeto `Runnable` se optimiza y no se materializa: su constructor se verifica, no se ejecuta.

El ejecutable generado recibe un número de repeticiones entre 0 y 10.000; lanza cuatro tareas Rayon, y el hilo principal ejecuta el `tick` el mismo número de veces, esperando los resultados antes de leer. El pool y las esperas son **scheduling Rust de este modo experimental**, no traducción de llamadas Java a `ForkJoinPool`, ni implementan Future, excepciones generales, shutdown o ciclo de vida Java. El resultado no depende de JVM externa, pero el JDK sí se usa para el oráculo de prueba. Ejemplo de interfaz:

```sh
mc-aot shared-worker-demo server.jar net/minecraft/test/WorkerEntry shared net/minecraft/test/IncrementTask ./worker tick read
./worker 1000
```

Con las opciones excluyentes `--ticktask-wrapper` o `--util-named-wrapper`, se valida el hash y bytecode del `TickTask` o `Util$4` oficial y se traduce su `run()` de reenvío a la tarea acotada anterior. Ambas capturas deben ser conocidas y no nulas; este modo no materializa los wrappers, no implementa `TickTask.getTick`, colas o programación por ticks, ni `Util.name`, `toString`, despacho de subclases o identidad observable. `Util$4` se usa en la rama de `DEBUG_NAMED_RUNNABLES` de `Util.name`, que aquí **no se ejecuta**. La prueba Java instancia las clases oficiales, pero el pool y la construcción son controlados externamente. `TickTask` tampoco representa que el servidor lo envíe a ForkJoinPool. Para verificar los hashes al traducir hace falta `sha256sum`; no se necesita al ejecutar el binario.

El fixture de la prueba `tests/check-shared-worker-bytecode.py` compara 32 ejecuciones Java 25/Rust (incluido desbordamiento `int`), otras 31 utilizando el bytecode oficial `QuartPos.toBlock`, y rechaza 18 variantes fuera de perfil, una versión modificada de QuartPos y argumentos inválidos (`analysis/shared-worker-bytecode-validation.log`). No se han certificado clases completas ni se ha conectado este modo a `Main`. Una auditoría encontró cero formas directas y tres wrappers de reenvío por interfaz entre los 31 métodos `run()V` de instancia del JAR interno, sin contar lambdas dinámicas ni bibliotecas (`analysis/runnable-run-shape-audit.log`). Los dos wrappers soportados tienen 31 ejecuciones diferenciales Java/Rust cada uno, ambos con `QuartPos.toBlock` oficial; solo se prueba `run`, no la clase completa.

## Experimento interno de campos compartidos

El runtime numérico permite convertir de forma explícita y opt-in un objeto de proyecto ordinario a almacenamiento de campos `Arc<Mutex<...>>` sin cambiar su índice ni copiar el vector de campos. Un handle interno expone únicamente lectura, escritura e incremento atómico experimental de campos `int`; se comprueba identidad y pertenencia al heap, y objetos especiales se rechazan. No se usa por defecto ni se puede activar desde Java. Una prueba con bytecode traducido por el backend principal y tareas Rust/Rayon verificó identidad y actualizaciones acotadas; se comparó también con un oráculo Java bajo sincronización (`analysis/numeric-object-sharing-validation.log`). La prueba incluye además 64 consultas secuenciales a un `FeatureFlagUniverse` oficial sin modificar con y sin compartir sus campos. **Este puente, por sí solo, no traduce tareas Java a Rayon, no comparte el resto del heap ni implementa un modelo de memoria Java multihilo general.** El modo acotado descrito arriba sí traduce un patrón de tarea sobre este puente. El incremento atómico del harness no significa que `i++` Java sea atómico. Desde el heap propietario se pueden resolver campos referencia a otros objetos ordinarios compartidos preservando alias, ciclos y null; no se exponen índices crudos ni se escriben referencias desde los workers. Se contrastaron 96 casos sintéticos y otros 96 con tres clases oficiales de feature flags, más una prueba controlada de Rayon (`analysis/numeric-shared-references-validation.log`). Arrays, String y demás destinos especiales se rechazan en ese helper; no existe navegación de referencias desde workers. El `SharedObj` tiene un monitor reentrante experimental común al bytecode numérico y a tareas Rust/Rayon en la prueba; se rechaza compartir un objeto cuyo monitor monohilo ya está adquirido. Se contrastaron 96 resultados y 20 rondas de 5.000 incrementos protegidos (`analysis/numeric-shared-monitors-validation.log`). `wait`/`notify`, interrupciones y monitores de clases no están implementados por este puente. Ver `analysis/heap-bridge-design.md` para el alcance y las pruebas.

## `Enum.valueOf`: perfil restringido

`Enum.valueOf(Class,String)` admite únicamente enums de proyecto registrados que heredan directamente de `Enum`, con `$VALUES` privado/estático/final/sintético y `values()` público/estático con forma javac verificada (carga, clone, cast, retorno). Inicializa la clase y crea un directorio por clase con una instantánea de las referencias de nombres y constantes, contabilizada en el límite experimental de heap; las coincidencias se resuelven por unidades UTF-16. Para un nombre null genera NPE tras la inicialización; para nombres ausentes en clases top-level sin `$`, genera IAE con mensaje. Los nombres ausentes en clases que contienen `$` abortan por falta de nombre canónico fiable. Clases no registradas/no enum, `values()` distinto, el array aún no disponible (incluida reentrada durante `<clinit>`), o arrays y constantes fuera del perfil abortan; no se traducen a excepciones Java inventadas. Literales JDK fuera de perfil pueden rechazarse al compilar. No es compatibilidad general de enums ni reflexión.

Se compararon 144 casos sintéticos y dos consultas de inicialización fallida con Java 25, incluyendo identidad, nombres Unicode, subclases por constante y errores. Una prueba adicional comprueba la instantánea tras mutar `$VALUES` y rechaza un `values()` alterado. Otras 180 consultas usan tres clases **sin modificar** del JAR oficial, `PacketFlow`, `PushReaction` y `ChunkType`, con hashes verificados (`analysis/real-minecraft-enum-valueof-validation.log`). Solo cubren este subconjunto; no certifican clases completas. El probe Eula con proveedor avanzó hasta el siguiente bloqueo de compilación, `Exception.toString`, y no ejecutó Eula (`analysis/real-eula-enum-valueof-attempt.log`).

## Inicialización entre clases: experimento monohilo

`multi-static-demo` usa la misma interfaz de operaciones que `static-demo`, pero registra varias clases del servidor o sus bibliotecas alcanzadas por operaciones estáticas y creación de objetos. Prepara los campos y ejecuta cada inicializador al primer uso, una sola vez; un uso recursivo de una clase que se está inicializando ve sus campos preparados o ya modificados. Las clases deben heredar directamente de `Object`, salvo las subclases directas restringidas de `InheritableThreadLocal` y los enums finales directos indicados arriba; pueden implementar interfaces transitivas inspeccionadas en el JAR, o `Runnable`, `Cloneable` y `Serializable`. Se inicializan las superinterfaces que declaran métodos no abstractos y no estáticos; el despacho de interfaz está cerrado a implementaciones directas precompiladas. No hay despacho general, defaults heredados ni herencia general; existen intrínsecos específicos de colecciones. Campos de descriptor de referencia pueden conservar `null` o referencias representadas por el subconjunto; esto no implementa los objetos de sus tipos automáticamente. `volatile` solo funciona con semántica monohilo. Límite: 256 clases. Admite handlers del subconjunto y conserva el estado erróneo de una clase tras un fallo de inicialización, pero no reproduce causas, mensajes o stack traces; sus monitores ordinarios son solo monohilo; fuera del puente experimental descrito arriba no tiene sincronización multihilo, ni modelo JVM general. Las lecturas `@campo` son instrumentos de prueba, no reglas de acceso Java; no presentan objetos arbitrarios.

```sh
cargo run -- multi-static-demo ../downloads/server-26.3.jar net/minecraft/world/level/biome/BiomeManager ./biome-multi '@CHUNK_CENTER_QUART' I '@ZOOM_BITS' I '@ZOOM' I '@ZOOM_MASK' I
./biome-multi 0 1 2 3
# 2, 2, 4, 3 (uno por línea)
```

Ejemplo de propiedades restringidas para un programa generado, equivalente al valor `-Dslf4j.example=valor` en una JVM de referencia:

```sh
MC_AOT_JAVA_PROPERTIES='slf4j.example=valor' ./programa <operaciones>
```

Varias entradas se separan por saltos de línea; las claves y valores de configuración deben ser UTF-8 y los valores no pueden incluir saltos de línea. Las mutaciones son locales al proceso. Solo `slf4j.*` está implementado; `java.version`, `user.dir` y otras propiedades fallan explícitamente.

Para inspeccionar un array estático con `@campo`, los arrays primitivos se muestran como listas de enteros (booleanos 0/1 y `char` como unidad UTF-16). Un `String[]` se muestra como `sarr16:[x<hex UTF-16>,n,...]`, con `n` para null y cuatro dígitos hexadecimales por unidad; es salida diagnóstica distinta del formato UTF-8 de entrada. Esto representa incluso sustitutos aislados.

```sh
./examples/rcon-hex-static 0
./examples/dry-foliage-static 1 '[1,2,3]' 0
# [48,49,...,102]  /  OK y luego [1,2,3]
```

El filtro ampliado encontró 99 candidatas con campos primitivos, cadenas o arrays admitidos. Compilaron 92 programas de un campo: las 92 lecturas coincidieron con Java, incluidas 18 cadenas y cuatro programas con `<clinit>`; no prueban las clases completas (`../analysis/audit-static-references.json`, `../analysis/static-reference-sweep.json`).

Una auditoría por forma encontró 75 clases con campos estáticos exclusivamente primitivos; compiló 71 programas de lectura de un campo, solo uno con `<clinit>`. Sus 284 lecturas coincidieron por muestreo con Java 25 (`../analysis/audit-multi-static.json`, `../analysis/multi-static-sweep.json`). No comprueba todas las operaciones ni certifica ninguna clase.

## Inspección y dependencias (no es traducción)

El lector Rust analiza las **7,762 clases** y sus descriptores de campos y métodos. La pasada estructural contó 69,821 métodos con `Code`, 1,315,735 instrucciones, 55,562 saltos y 1,931 entradas de manejador sin errores; clases, métodos e instrucciones coinciden con el inventario Python independiente. Revisa límites de instrucciones, destinos de salto y rangos de handlers, pero **no verifica los tipos de pila, inicialización, semántica JVM ni seguridad**. Es solo para archivos de confianza. Se contrastaron 219 descriptores y 165 referencias `Class` de siete clases con `javap` 25; una prueba sintética también comprueba `MethodType`, MUTF-8 y rechazos de archivos truncados.

El grafo registra referencias desde constantes `Class`, `NameAndType`, `MethodType` y descriptores de campos y métodos. No analiza atributos genéricos `Signature`, anotaciones, reflexión, carga dinámica ni recursos; puede incluir código nunca ejecutado. Desde `Main` su cierre estático contiene **7,253 clases internas**, no clases traducidas ni necesariamente usadas al arrancar. Al cruzar las referencias de ese cierre con los nombres de las 39 bibliotecas del bundle (con SHA-256 comprobado), 643 nombres aparecen en ellas, 451 tienen prefijo parecido al JDK y no quedan nombres en la categoría restante. Los prefijos no comprueban que exista la clase y el tratamiento de JARs multi-release es una aproximación. Ver `../analysis/dependency-summary.json`.

```sh
# Clase individual (bundle o JAR interno)
cargo run -- inspect ../downloads/server-26.3.jar net/minecraft/server/Main
# Regenera índice y grafo comprimido a partir del JAR interno
./index-jar.sh
python3 dependency-summary.py
# Comprobaciones opcionales con JDK 25
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-index.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-inspect.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-graph.py
```

Salida: `../analysis/class-index.tsv`, `../analysis/class-dependencies.tsv.gz` y `../analysis/dependency-summary.json`. El script acepta rutas opcionales de JAR, índice y grafo, en ese orden; el grafo siempre se escribe comprimido con gzip. También se puede invocar `index-dir` o `graph-dir` con un directorio de `.class` ya extraídos; imprimen TSV en stdout y estadísticas en stderr.

## Probar

Desde esta carpeta:

```sh
cargo test
# Lee un entero little-endian desde un array Java byte[].
cargo run -- compile ../downloads/server-26.3.jar net/minecraft/server/rcon/PktUtils intFromByteArray '([BII)I' ./rcon-int
./rcon-int '[1,2,3,4]' 0 4
# 67305985

# Empaqueta coordenadas de chunk en un long, sin JVM en ejecución.
cargo run -- compile ../downloads/server-26.3.jar net/minecraft/world/level/ChunkPos pack '(II)J' ./chunk-pack
./chunk-pack -1 4
# 21474836479

cargo run -- compile ../downloads/server-26.3.jar net/minecraft/util/LightCoordsUtil lightCoordsWithEmission '(II)I' ./emission
./emission 16711680 5

cargo run -- compile ../downloads/server-26.3.jar net/minecraft/server/commands/FillBiomeCommand quantize '(I)I' ./quantize
./quantize -9
# -12

cargo run -- object-demo ../downloads/server-26.3.jar 'net/minecraft/world/level/LevelHeightAccessor$1' ./height --default net/minecraft/world/level/LevelHeightAccessor getMaxY
./height 384 -64 getHeight getMinY getMaxY
# 384
# -64
# 319

cargo run -- multi-demo ../downloads/server-26.3.jar 'net/minecraft/world/level/LevelHeightAccessor$1' 'net/minecraft/world/level/levelgen/BelowZeroRetrogen$1' net/minecraft/world/level/LevelHeightAccessor getMaxY ./height-heap
./height-heap new 0 384 -64 new 1 copy 0 eq 0 2 call 2 getMaxY call 1 getMaxY
# 0, 1, 2: referencias creadas (una por línea)
# 1: la referencia 2 apunta al mismo objeto que la 0
# 319: getMaxY del primer tipo
# -1: getMaxY del segundo tipo

cargo run -- reference-demo ../downloads/server-26.3.jar net/minecraft/world/flag/FeatureFlagUniverse toString ./flag-ref
./flag-ref string Mundo new 0 get 1 eq 0 2 text 2
# 0, 1, 2: referencias creadas (una por línea)
# 1: el getter devolvió la misma referencia String
# Mundo
```

Los argumentos de array de la CLI se escriben como `null`, `[]` o `[1,2,-3]`, con elementos en el rango del tipo de la firma. `@0`, `@1`, etc. reutilizan la referencia del primer, segundo, etc. argumento de array **anterior**, empezando en cero; así se puede probar identidad y alias. Los valores del array se almacenan en el heap experimental de esa ejecución. La CLI solo puede recibir arrays primitivos o `String[]` y no puede devolver arrays; las llamadas internas de `multi-static-demo` admiten además arrays de objetos de los tipos acotados descritos. No se admiten multidimensionales, `float[]` ni `double[]`.

Para `String` la CLI usa `null` o `s:contenido` (por ejemplo `s:null` es el texto, no `null`). Para `String[]`, usa `null` o `sarr:[elementos]`: cada elemento es `n` para null o `x` seguido por bytes UTF-8 en hexadecimal; `x` solo representa la cadena vacía. Por ejemplo `sarr:[x686f6c61,n,xf09f9a80]` significa `["hola", null, "🚀"]`. Los alias `@0`, etc. también funcionan con arrays de cadenas. Un retorno `String` se imprime como texto, y `null` como `null`; cadenas con sustitutos UTF-16 aislados se imprimen con `?`, por lo que esta interfaz no distingue todos los retornos ni representa sustitutos aislados como argumentos. En `main(String[])` los argumentos son los del proceso tal cual, no este formato, y no se imprime el `OK` de los métodos `void`. La salida está orientada a UTF-8 y no pretende reproducir todas las configuraciones de `PrintStream`.

```bash
./examples/identifier-valid-path 's:foo/bar'  # 1
./examples/identifier-valid-namespace 's:..' # 0
./examples/recipe-first-nonempty 's:  a'     # 2
./examples/light-neighbor-count 0 26         # 26
```

Para combinar las tres clases en el mismo heap experimental, añade `--reference net/minecraft/world/flag/FeatureFlagUniverse toString` después de la ruta del binario en el comando `multi-demo`. El script `build-examples.sh` genera ese ejemplo como `examples/combined-heap`.

Admite el bundle oficial o el JAR interno. Crea el binario indicado y escribe el Rust generado junto a él con sufijo `.rs`. Para regenerar todos los ejemplos en tu plataforma:

```sh
./build-examples.sh
```

Para comprobarlos con Java 25, tras compilarlos para tu máquina:

```sh
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-nbt-exceptions.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-jdk-properties.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-ascii-ignore-case.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-unicode-ignore-case.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-classloader-identity.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-reflection-catches.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-object-arrays.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-final-enums.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-real-slf4j-enums.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-stringbuilder.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-string-format-basic.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-system-streams.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-monitors.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-jdk-arraylist.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-init-errors.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-jdk-inheritable-local.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-jdk-collections.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-jdk-threadlocal.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-dup-x.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-objects.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-object-init.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-object-guards.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-volatile.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-interfaces.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-bundle-libraries.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-float-preparation.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-references.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-string-constant.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-array-types.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-static.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi-static-guards.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-exceptions.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-exception-static.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-exception-table.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-string-main.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-string-guards.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-demo.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-constants.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-static-guards.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-guards.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-object.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-multi.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-reference.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-wide.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-numeric-stack.py
JAVA_HOME=/ruta/a/jdk-25 python3 tests/check-numeric-guards.py
cd ../graal-test
JAVA_HOME=/ruta/a/jdk-25 python3 compare-real-multi-objects.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-static-arrays.py
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-static-references.py
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-static-float-preparation.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-multi-static-init.py
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-multi-static.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-static-init.py
# Primero ejecuta ../mc-aot/audit-static-init.py para regenerar el barrido.
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-static-init.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-neighbor-exception.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-strings.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-arrays.py
# Inicializa registros solo en la JVM, sin arrancar el servidor; requiere memoria.
JAVA_HOME=/ruta/a/jdk-25 python3 compare-map-array.py
# Primero ejecuta ../mc-aot/audit-arrays.py para regenerar la lista del barrido.
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-arrays.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-long.py
# Primero ejecuta ../mc-aot/audit-long.py para regenerar la lista del barrido.
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-long.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-switch.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-small-args.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-mth.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-object.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-multi.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-reference.py
JAVA_HOME=/ruta/a/jdk-25 python3 compare-combined.py
JAVA_HOME=/ruta/a/jdk-25 python3 sweep-references.py
```

Para inventariar instrucciones y ejecutar la auditoría de compilación de todos los métodos con la firma admitida:

```sh
python3 scan-bytecode.py ../downloads/server-26.3-inner.jar > inventario.json
python3 audit.py
python3 audit-small-args.py
python3 audit-long.py
python3 audit-static-references.py
python3 audit-multi-static.py
python3 audit-exceptions.py
python3 audit-strings.py
python3 audit-arrays.py
python3 scan_static_init.py
python3 audit-static-init.py
python3 audit-objects.py
python3 audit-references.py
```

La auditoría de referencias encontró 17 pares candidatos constructor/getter `String`; seis compilaron en seis clases. Los seis se probaron contra Java para identidad y `null`, pero no son clases completas. Informe: `../analysis/audit-references.json`.

La auditoría de objetos encontró **dos programas de instancia compilables** bajo un filtro muy restrictivo de métodos declarados. No certifica los métodos heredados ni clases completas; el resultado está en `../analysis/audit-objects.json`.

La auditoría original encontró 202 métodos con argumentos `int` y retorno primitivo pequeño: **160 compilaron** en 73 clases. La auditoría con al menos un argumento `boolean`, `byte`, `char` o `short`, encontró 47 candidatos y **47 compilaron** en 20 clases. La auditoría de firmas que contienen `long` encontró 63 candidatos y **40 compilaron** en 15 clases. La auditoría adicional de arrays encontró **15 candidatos y los 15 compilaron**, en cuatro clases; 14 se contrastaron en 336 muestras y el restante en 83 casos con bootstrap JVM, como se describe arriba. En conjunto son **262 métodos de 327 candidatos**, repartidos en 99 clases con al menos un método que compila. Los 40 métodos de la auditoría `long` se contrastaron en 960 muestras con Java 25, pero esto no demuestra equivalencia completa. Informes: `../analysis/audit-static-primitives.json`, `../analysis/audit-small-args.json`, `../analysis/audit-long.json`, `../analysis/audit-arrays.json`, `../analysis/long-sweep.json` y `../analysis/array-sweep.json`; **cero clases completas certificadas**.

La auditoría `audit-strings.py` seleccionó 310 métodos con `String`/`String[]` en la firma y los demás tipos dentro del subconjunto; 139 compilaron en 94 clases. El filtro incluye retornos `String` y métodos sin argumentos que devuelven una cadena, y no demuestra que los métodos funcionen en todos los casos ni que las clases estén completas. Solo cuatro métodos reales de esta auditoría se contrastaron en la prueba de cadenas descrita arriba. Informe: `../analysis/audit-strings.json`.

La auditoría `audit-exceptions.py` halló diez métodos estáticos del JAR con tabla de excepciones y firmas del subconjunto. Siete tienen tipos catch incorporados o de Minecraft, pero **ninguno compila completo**: aún aparecen dependencias como `ServerSocket`, `System.getProperty`, campos estáticos o firmas externas. `Main` está entre los candidatos pero falla en un campo estático de referencia; otros tienen tipos de bibliotecas no admitidos. Es un recuento acotado, no una estimación de clases completas; informe `../analysis/audit-exceptions.json`.

## Límites importantes

- Solo métodos estáticos con retorno `void`, `String`, `int`, `long`, `boolean`, `byte`, `char` o `short`, con argumentos de esos tipos, `String[]` o arrays primitivos unidimensionales, y un subconjunto de instrucciones. En `compile`/`static-demo`, las llamadas se limitan a los equivalentes `Math` listados y métodos compatibles en la clase actual o bajo `net/minecraft/`; `multi-static-demo` puede resolver también clases admitidas de bibliotecas del bundle. En `compile`/`static-demo` se rechaza la recursión; `multi-static-demo` admite recursión con guarda experimental explícita de profundidad 256, no `StackOverflowError` Java.
- La vía principal solo maneja los objetos especiales `String` y `System.out`, no objetos arbitrarios. `object-demo` solo admite una instancia concreta, herencia directa de `Object`, campos `int`, un constructor y métodos declarados `()I` muy simples; opcionalmente incorpora un único default `()I` de una interfaz directa.
- `multi-demo` admite referencias compartidas, `null`, varias instancias y selección entre dos tipos fijados al compilar; opcionalmente integra una tercera clase con un campo `String`. Usa un vector sin recolección de basura y despacho generado: no es un heap JVM, no tiene hilos ni carga dinámica y **no admite campos de referencia arbitrarios**. `reference-demo` traduce solo el constructor `(String)V` y el getter seleccionado, no los demás métodos. `String` es un valor Rust opaco con identidad, no una implementación completa de Java. Las excepciones `null` no son capturables. El resto de métodos heredados sigue sin implementarse.
- Los arrays de objetos son solo los tipos acotados descritos; no hay arrays multidimensionales, arrays de `float` o `double`, sincronización entre hilos, carga dinámica ni la mayoría de tipos Java. Las tablas de excepciones admiten solo el subconjunto indicado; excepciones no capturadas terminan el proceso y faltan tipos, causas, stack traces y semántica JVM general. La pila numérica comprueba categorías al ejecutar, pero no es un verificador JVM de tipos ni de inicialización.
- `compile` y `compile-numeric` no ejecutan inicializadores de clase; solo `static-demo` y `multi-static-demo` los manejan en los casos restringidos descritos. Esto limita incluso la equivalencia de los métodos individuales. Se rechazan instrucciones no admitidas; un binario anterior del mismo nombre puede permanecer si una compilación posterior falla.
- La máquina de estados comprueba límites de saltos, pero no verifica todo el bytecode JVM. El proyecto es para archivos de confianza, **no** es un sandbox.
- El punto de entrada real del servidor sigue sin ser compilable: la compilación falla al acceder al campo estático de referencia `SharedConstants.CURRENT_VERSION`; el modo multiclase alcanza código de logging, pero rechaza la herencia de `org.slf4j.helpers.NOPLogger`; la reflexión general de métodos, Log4j y otras dependencias siguen pendientes (`../analysis/main-multi-static-attempt.log`). No hay garantía de compatibilidad total ni de mejora de rendimiento.

Consulta las condiciones de Mojang y terceros antes de redistribuir archivos o trabajos derivados.

### Avances recientes del modo multiclase

Se admiten inicializadores de superinterfaces según el orden JVM para interfaces con métodos no abstractos/no estáticos, recursión acotada, un `LinkedHashSet` de `String`/`null`, `ConcurrentHashMap.values` monohilo y copias a `ArrayList` con límites explícitos. El despacho de interfaces solo usa implementaciones directas precompiladas; defaults heredados abortan. El proveedor SLF4J real se descubre y construye mediante registro explícito; una prueba aislada posterior ejecutó `initialize` con configuración predeterminada, sin certificar el funcionamiento completo de Log4j. `ClassLoader.getResources` solo admite la comprobación específica del recurso antiguo de SLF4J y rechaza recursos presentes u otros nombres. Véase `../PLAN-ARRANQUE.md` para pruebas y límites. Ninguna prueba certifica clases completas; el servidor aún no arranca.

Reflexión de métodos restringida y opt-in: `MC_AOT_REFLECT_METHODS='clase/interna#metodo#(Lclase/Argumento;)V|clase/interna#otro#()Ljava/lang/String;'`. Se admiten solo métodos públicos directos registrados, con cero o un parámetro de proyecto y retorno `void` o referencia; tipos, firmas y métodos desconocidos se rechazan explícitamente. La prueba `tests/check-reflection-methods.py` compara rutas concretas contra Java, no implementa reflexión general.

### Estado adicional de reflexión y Log4j

En `multi-static-demo`, `getDeclaredConstructor` se restringe a clases registradas y al constructor público vacío; los privados abortan. `Class.forName(String,boolean,ClassLoader)` exige `MC_AOT_STANDARD_SYSTEM_LOADER=1`, cargador estándar y clase de proyecto precompilada; no carga clases dinámicamente. `Class.asSubclass` utiliza la jerarquía registrada y aborta para tipos JDK no modelados. Construir `PrintStream` o `FileOutputStream` es una **guarda de aborto**, no una implementación de E/S. Los cuatro perfiles tienen pruebas en `run-regressions.sh`. El probe Eula con bibliotecas oficiales se detiene al compilar `Comparator.comparing(Function)`; Main sigue sin backend ForkJoinPool integrado. No se ha ejecutado el servidor.

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
