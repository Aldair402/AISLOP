# Roadmap: servidor vanilla JAR → binario nativo en Rust

## Objetivo y estado

Traducir el JAR oficial del servidor Minecraft 26.3 a un ejecutable nativo **sin JVM externa**, hacerlo arrancar y validar completamente al menos **3.881 de las 7.762 clases** del JAR interno. El alcance es el comportamiento que Minecraft necesita; una dependencia Rust puede reemplazar una biblioteca Java solo con un adaptador comprobado. Este roadmap no presupone compatibilidad general con Java ni es una estimación de plazos.

**Hoy: 0 clases completas certificadas; 0 %. No existe un servidor nativo arrancable.** El último intento de `Main`, con `MC_AOT_DISABLE_JFR=1`, sigue detenido al compilar `new ForkJoinPool` desde `Util.makeExecutor` (`analysis/main-numeric-concurrent-graph-attempt.log`); no produjo ni ejecutó el servidor. El adaptador Rayon no está conectado automáticamente al backend principal ni a `Main`; pruebas opt-in enlazan ambos heaps para objetos registrados y su monitor. El último probe Eula real con proveedor registrado avanzó tras el perfil de `Enum.valueOf` y se detuvo al compilar `Exception.toString` (`analysis/real-eula-enum-valueof-attempt.log`); no ejecutó Eula. La última suite integral aprobada terminó con **300 etapas** y exit 0 (`analysis/full-regressions-numeric-concurrent-graph-ticktask.log`), incluidos ambos puentes y la variante TickTask; Rust pasó 59 unitarias y 25 de integración. Una integral intermedia se interrumpió para ampliar el perfil y otra falló en `check-static-array-types` por una advertencia de Java `hsperfdata` contaminando stdout (`analysis/full-regressions-shared-worker-wrappers.log`); el reintento correcto usó el mismo JDK con `-XX:-UsePerfData`, reproducible con `mc-aot/tools/java-no-perf-wrapper.sh`.

**Decisión actual:** aparcar la integración de `log4rs` por ahora. Su prototipo queda conservado sin conectarlo ni alterar el logger real. El logging sigue siendo un requisito para arrancar y se retomará cuando corresponda; no se ocultarán errores ni se usará un logger ficticio.

## Reglas de avance

- Cada cambio: prueba diferencial Java 25 con entradas normales y límites, pruebas de error y guardas para rutas no implementadas; registrar versión de JDK, hashes y comandos. Para concurrencia, incluir carreras repetidas y comprobar invariantes, no exigir un orden que Java no garantiza.
- Un éxito de compilación, un inventario, un método probado o un fixture con stubs **no equivale a una clase completa** ni a un arranque. No convertir abortos internos en excepciones Java inventadas.
- Mantener reproducible el bundle y la versión: SHA-256 del JAR interno `a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6`. Evitar sobrescribir evidencia y no ejecutar binarios antiguos tras un fallo del compilador.
- Identificar configuración y perfiles del host y del servidor: opciones JVM comparables, JFR/Tracy, classpath, archivos, zona horaria y red. El modo de producción no deberá necesitar que Java esté instalado; Java se permite para construir oráculos de prueba.
- Los hitos son puertas verificables, no promesas de fecha. Un bloqueo descubierto reordena los trabajos sin rebajar los criterios.

## Hitos

### 1. Base reproducible y medición honesta — en curso

1. Conservar la suite integral y los probes de arranque; cada fallo debe señalar el primer bloqueo, contexto y configuración.
2. Inventariar cada clase por hash, campos, métodos **incluidos constructores y privados**, inicializador, superclases/interfaces, efectos y dependencias. Registrar evidencias y faltantes por separado.
3. Empezar con `QuartPos`: `analysis/quartpos-evidence-report.json` registra evidencia parcial de **5/6 métodos y 4/4 campos**; el constructor privado no está contrastado. El script `mc-aot/tools/class-surface-evidence.py` comprueba hashes y correspondencia con miembros declarados, pero **no certifica semántica**. Un hash solo identifica un archivo, no demuestra que su contenido sea verdadero.
4. Diseñar un registro de clases completas verificadas con revisión y reproducibilidad; no alimentar el contador a partir de este inventario parcial.

**Puerta:** reconstrucción, pruebas y reportes reproducibles; el contador permanece 0 hasta que una clase cumpla el criterio de clase completa de abajo.

### 2. Unificar el runtime concurrente y el backend principal

1. Documentar diferencias entre el heap monohilo de `numeric_runtime.inc` y `SharedHeap`/frames/Rayon; decidir una representación única o puente seguro de identidad, referencias, campos, monitores, clases inicializadas y excepciones.
2. Crear pruebas integradas pequeñas antes de tocar Main: la misma instancia compartida entre llamador y tareas, publicación de estáticos, alias, monitores reentrantes, inicialización única, ejecución de callbacks y propagación de fallos. La primera prueba Rust de `SharedHeap` + `ClassInit` + Rayon pasó 20 rondas/10.000 incrementos (`analysis/rayon-shared-init-invariants.log`), pero no utiliza el backend principal. Un nuevo experimento opt-in mueve campos de objetos ordinarios del heap numérico a almacenamiento compartido; una prueba ejecutó bytecode traducido por el backend principal junto a tareas Rust/Rayon durante 20 rondas de 4.000 incrementos (`analysis/numeric-object-sharing-validation.log`). Una segunda prueba resuelve referencias entre objetos ordinarios desde el heap propietario, con alias/ciclos, 20 rondas Rayon y 96 resultados sobre clases oficiales de feature flags (`analysis/numeric-shared-references-validation.log`). Un tercer experimento comparte el monitor reentrante del mismo objeto entre bytecode principal y tareas Rust/Rayon: 20 rondas de 5.000 incrementos protegidos (`analysis/numeric-shared-monitors-validation.log`). Un modo nuevo traduce un patrón exacto de `Runnable.run` que incrementa bajo monitor el mismo objeto del backend principal, con cuatro tareas Rayon y comparaciones Java incluso con `QuartPos.toBlock` oficial (`analysis/shared-worker-bytecode-validation.log`). También traduce el reenvío de `TickTask.run` o `Util$4.run` oficiales cuando sus hashes y bytecodes coinciden, con capturas conocidas no nulas; ni los objetos wrapper, ni `getTick`, ni las colas, ni `Util.name` ni `toString` se implementan. El scheduling es Rust controlado: no traduce las llamadas Java a `ForkJoinPool` ni materializa el objeto Runnable. **Ese modo no conecta el `SharedHeap` previo; los workers no navegan referencias y el resto del heap no se comparte.** Una prueba posterior sí enlaza ambos backends para un objeto int, como se describe abajo. Ver `analysis/heap-bridge-design.md`. Mantener guardas para las semánticas que falten.
3. Conectar el `ForkJoinPool` usado por `Util.makeExecutor`, incluido constructor de cuatro argumentos, factory y handler reales, workers y ciclo de vida, no solo `ForkJoinPool(int)` de los fixtures. Ensayar `execute`/`submit`, `join`, `shutdown` y esperas que usa Minecraft; estudiar interrupciones, cancelación y rechazos antes de habilitarlos.
4. Repetir el probe de `Main` real y registrar el siguiente bloqueo. Si se necesita logging para la factory o callbacks, volver al hito 3 sin sustituirlo por una simulación.

**Puerta:** bytecode real de la ruta de executor ejecutado con tareas y worker reales, bajo diferenciales y pruebas de estrés; el backend principal lo utiliza. Esto no implica que Main arranque.

### 3. Dependencias reales para la ruta de inicio

1. Resolver la inicialización del proveedor y del logger con la ruta Java traducida o retomar un adaptador Rust después de verificar semántica. Preservar nombres, niveles, mensajes, `Throwable`, destinos y cierre; el XML de Mojang incluye filtro, consola, archivo rotativo, Queue y listener. Rechazar configuraciones no implementadas.
2. Continuar Eula real y sus archivos, clases de configuración, recursos, classpath, reflexión, excepciones y opciones siguiendo los bloqueos observados. Evitar implementar dependencias ajenas a la ruta de Minecraft por compatibilidad general.
3. Controlar recursos nativos de forma acotada y verificable: rutas, propiedades, red, reloj, paralelismo, memoria y terminación; no confundir configuración desactivada con soporte de JFR/Tracy activo.

**Puerta:** probe Eula traducido con dependencias reales o adaptadores comprobados, sin stubs de comportamiento, que compare aceptación y rechazo, errores de archivo, efectos y logging frente a Java. Todavía no equivale a un servidor.

### 4. Primer arranque y ciclo de vida

1. Compilar `Main.main` desde el bundle oficial, enlazar todo en un ejecutable autocontenido y ejecutar sin JVM externa. Probar en directorio aislado con configuración y aceptación de EULA explícitas de prueba; no descargar ni abrir servicios arbitrarios.
2. Exigir no solo un mensaje de «listo»: creación de mundo, estado estable, escucha en puerto de prueba, conexión y protocolo básico con cliente de prueba autorizado, comandos básicos, guardado y recarga.
3. Ejercitar parada normal, cierre de executors y archivos, errores de configuración y reinicio. Comparar resultados y efectos relevantes con Java; registrar versiones, configuración y fallos.

**Puerta:** proceso nativo arranca, responde a una interacción real y termina/reinicia correctamente, con evidencia reproducible. No se infiere rendimiento ni compatibilidad total del servidor.

### 5. Clases completas: 1 → 777 → 1.941 → 3.881

Trabajar en paralelo con el arranque por familias necesarias para Minecraft y dependencias de alto impacto: primitivas/coordenadas; colecciones y serialización; registries y recursos; mundo/chunks; red y protocolo; entidades y lógica del servidor. Priorizar por el grafo de Main y rutas observadas, sin confundir alcanzabilidad estática con ejecución real. Para cada lote, registrar las clases completas nuevas, pendientes y regresiones; no extrapolar desde métodos aislados.

- **Primer hito:** 1 clase completa con paquete de evidencia y revisión reproducible.
- **10 %:** al menos 777 clases completas.
- **25 %:** al menos 1.941 clases completas.
- **50 %:** al menos **3.881 clases completas**.

**Puerta final:** superar el hito 4 y el de 3.881 clases, sin JVM externa. Una clase contada debe cumplir los criterios completos; las parciales se mantienen en otro registro.

## Qué significa «clase completa y validada»

Para el **JAR y configuración fijados**, cada clase contada debe tener como mínimo:

1. Superficie declarada reconciliada con el classfile: todos los campos y métodos, constructores, métodos privados/sintéticos/bridge, `<clinit>` si existe, flags, herencia e interfaces. Incluir comportamiento heredado y llamadas de los consumidores relevantes.
2. Traducción y dependencias necesarias implementadas para las operaciones de esa clase, sin guardas de funcionalidad pendiente en las rutas admitidas ni stubs que oculten efectos; cubrir inicialización, identidad, tipos, despacho, excepciones y cambios de estado cuando apliquen.
3. Evidencia diferencial frente a Java 25 de la superficie y secuencias de estado: límites, entradas adversas, errores, null y alias; para dominios grandes, combinar pruebas dirigidas, propiedades y análisis del bytecode. Añadir concurrencia, recursos, I/O y reflection cuando sean observables. Una muestra no prueba por sí sola equivalencia universal.
4. Lista explícita de supuestos y entornos, hashes del JAR, clase, herramientas y pruebas; resultados verificables de una ejecución fresca y revisión de vacíos conocidos. Las exclusiones o perfiles limitados se documentan como **parciales**, no se cuentan como clase completa.
5. Reejecución automatizada y sin regresiones. Una certificación aquí significa que superó estos criterios de validación definidos, **no una prueba matemática de equivalencia para todas las ejecuciones posibles**.

## Avance adicional: enums reales, sin certificación

Se incorporó un perfil acotado de `Enum.valueOf` al backend principal: 144 resultados sintéticos, inicialización fallida, mutación de `$VALUES` y 180 consultas sobre tres enums oficiales de Minecraft coinciden con Java 25 en los casos observados. Reentrada con `values` aún no disponible, `values()` no canónico, nombres ausentes de clases con `$` y otros casos no modelados abortan explícitamente; el directorio cuenta contra el límite de heap. Ver detalles y pruebas en `mc-aot/README.md` y `analysis/{enum-valueof-profile-validation,enum-valueof-cache-validation,real-minecraft-enum-valueof-validation}.log`. Ninguna clase queda certificada por estos resultados. El probe Eula con proveedor supera el bloqueo de compilación anterior de `Enum.valueOf` pero se detiene en `Exception.toString`; no ejecuta Eula ni Main (`analysis/real-eula-enum-valueof-attempt.log`). Log4rs sigue aparcado y la prioridad del roadmap continúa siendo el puente del runtime y ForkJoinPool.

## Puente entre los dos backends — primer objeto compartido

`SharedHeap` admite un objeto externo bajo un contrato interno de campos `int` o referencias validadas y monitor, y `numeric_concurrent_bridge.inc` adapta un objeto ordinario del heap numérico **sin copiar sus campos ni su monitor**. `check-numeric-concurrent-bridge.py` combina explícitamente el Rust generado por ambos backends: el principal ejecuta `Owner.tick/read`, mientras el backend concurrente traduce el bytecode Java que crea un `ForkJoinPool`, crea cuatro `Runnable`, los envía, hace `join` y cierra el pool. Las tareas y el llamador usan el mismo objeto y monitor; `QuartPos.toBlock` es oficial. El test comprueba 20 rondas frente al resultado del oráculo Java 25, desbordamiento, alias, reentrada en ambos sentidos, bloqueo entre hilos, liberación al desenrollar, heap ajeno, límites de tipos y ejecución sin Java en PATH (`analysis/numeric-concurrent-bridge-validation.log`).

**Alcance:** la composición, el layout y la publicación del objeto se preparan en un harness Rust de prueba; `numeric_concurrent_bridge.inc` no se incluye automáticamente en el código generado y no traduce la llamada Java que une ambos heaps. El layout se verifica externamente contra el classfile (clase final directa de Object, sin interfaces/inicializador y un campo `I`); la etiqueta interna `V::I` no basta para distinguir `int` de `byte`, `char`, `short` o `boolean`. El contrato de identidad del adaptador es interno y confiable. Ese primer adaptador solo admite campos `int`. El segundo experimento de grafo descrito abajo admite referencias finales de lectura; no hay soporte general de referencias ni de otros campos, estáticos/clases unidos, inicialización concurrente general, excepciones Java de tareas, interrupciones, `wait`/`notify`, ni integración con `Main`. No se certifica ninguna clase completa.

### Referencia final entre objetos de ambos heaps

`numeric_concurrent_graph_bridge.inc` amplía la prueba a dos objetos `Node` finales del heap numérico registrados explícitamente en un `SharedHeap`; la tarea Java traducida navega `root.next` y modifica el segundo objeto bajo el mismo monitor que el backend principal. La composición del código, los layouts verificados por classfile, el registro de ambos objetos y la publicación siguen siendo un harness Rust, no instrucciones Java traducidas. El mapa de identidades es por sesión y heap; referencias no registradas, IDs de otro heap, layouts incompatibles, sesiones distintas para el mismo objeto y uso después de cerrar la sesión se rechazan. Las referencias son **solo de lectura**, no admiten subtipos, strings ni arrays; los campos `int` sí se comparten. Comparación frente a Java 25 en 20 rondas por variante con cuatro tareas, `QuartPos.toBlock` oficial, overflow y ejecución sin Java en PATH. La segunda variante materializa `TickTask` oficial y traduce su `run`/`getTick` antes de navegar la captura (`analysis/numeric-concurrent-graph-validation.log`, `analysis/numeric-concurrent-graph-ticktask-validation.log`). El fixture no demuestra que el servidor envíe TickTask a ForkJoinPool. No certifica clases ni inicia Main.

Las integrales posteriores se interrumpieron voluntariamente para incorporar el grafo y la variante TickTask (`analysis/full-regressions-numeric-concurrent-bridge.log`, `analysis/full-regressions-numeric-concurrent-graph.log`); no cuentan como aprobadas. La integral posterior con ambos puentes y la variante TickTask terminó con exit 0 y 300 etapas (`analysis/full-regressions-numeric-concurrent-graph-ticktask.log`).

## Capturas compartidas y TickTask en el backend concurrente

Con opt-in, el backend concurrente aislado materializa `Runnable` con referencia final a un objeto de proyecto final sin interfaces ni inicializador, y permite compartir ese objeto y su monitor entre la llamada principal y cuatro tareas con `ForkJoinPool` Java traducido a Rayon. Las pruebas añaden la `TickTask` oficial materializada (hash exacto), con `run` y `getTick`, que reenvía a un Runnable con captura, y `QuartPos` oficial: 28 comparaciones por variante (`analysis/rayon-java-captured-object-validation.log`, `analysis/rayon-real-ticktask-capture-validation.log`). No hay soporte general de excepciones Java, interrupciones, colas de ticks, subclases, integración con el heap numérico o `Main`, ni certificación completa de `TickTask`. El inventario de llamadas directas halló `MinecraftServer.wrapRunnable` → constructor y `MinecraftServer.shouldRun` → `getTick` (`analysis/ticktask-callers-current.log`); ninguno de esos métodos del servidor se ha traducido ni ejecutado en esta prueba, y `shouldRun` depende también de `tickCount` y `haveTime`.

## Prioridad tras el primer `Runnable` acotado

Una auditoría estructural encontró 31 métodos de instancia `run()V` en el JAR interno y **ninguno** con la forma exacta `aload_0; getfield; invokevirtual; return` del demo (`analysis/runnable-run-shape-audit.log`). Una segunda búsqueda halló tres wrappers de reenvío por interfaz: `TickTask`, `Util$4` y `StrictQueue$RunnableWithPriority`; el demo ahora incluye los `run()` de los dos primeros en condiciones controladas. No examina las lambdas dinámicas ni las bibliotecas, ni verifica elegibilidad general; no mide cobertura completa. La siguiente ampliación debe partir de bytecode de tareas y capturas reales (incluido `invokedynamic`) y de las llamadas a `Executor`/`ForkJoinTask`, no suponer que el patrón sintético desbloquea `Main`.

## Inventario de executors y futures

Una búsqueda estructural de llamadas directas en el JAR interno encontró 367 invocaciones en 97 clases y 250 métodos a los tipos seleccionados (`analysis/executor-direct-inventory.log`, `analysis/executor-direct-calls.tsv`). 327 tienen owner `CompletableFuture`, incluidas 44 llamadas a `completedFuture`, 36 a `join`, 33 a `supplyAsync` con executor y 29 a `thenApply`. Es un inventario de referencias, no demuestra rutas ejecutadas ni cobertura. 270 llamadas aparecen en métodos con al menos un `invokedynamic`, pero esto incluye concatenaciones y no identifica necesariamente una lambda. El bytecode de `Main.main` contiene una llamada directa a `CompletableFuture.get` en el offset 668; `WorldLoader.load` contiene `supplyAsync`, y `Util.sequence` usa `completedFuture`, `allOf` y `thenApply` (`analysis/util-main-bytecode-current.log`). Su presencia estática no prueba que se hayan ejecutado. La prioridad siguiente debe incluir futures, composición y errores observables, además de pools; no basta con soportar el constructor de ForkJoinPool. Se preparó un oráculo independiente de Java 25, 20 rondas, para nulidad e identidad, completar una sola vez, diferencias entre `get`/`join`, cancelación, `allOf`, callbacks, rechazo del executor, timeout e interrupción (`analysis/completable-future-java25-oracle.log`). **No existe aún el adaptador nativo ni una comparación diferencial**; este oráculo todavía no forma parte de la integral.

## Próximas acciones concretas

1. Validar el inventario parcial y sus guardas: `python3 mc-aot/tests/check-class-surface-evidence.py`. No contar `QuartPos` aún.
2. Ampliar el experimento opt-in del backend principal: automatizar y validar por classfile la selección del layout y la publicación entre ambos backends; permitir navegación segura desde workers y compartir demás tipos con identidad y pertenencia verificadas; unificar estáticos e inicialización antes de conectar tareas Java a Rayon desde Main. El modo de tarea Java solo cubre un patrón exacto, no traduce el pool Java ni comparte estáticos; ver `analysis/heap-bridge-design.md` y el diseño de monitores en `analysis/next-numeric-shared-monitor.md`.
3. Extender el probe del worker oficial más allá de `onStart`, sin ignorar `Util.LOGGER`, y determinar qué parte exige el logger antes de que una tarea real pueda ejecutarse. No activar Tracy silenciosamente.
4. Repetir la suite integral cuando se modifique el runtime. La última integral completa y las pruebas focalizadas se distinguen siempre en este archivo.

## Ejemplos generados y espacio

Los 63 ejecutables de ejemplo se conservaron localmente en `analysis/generated-examples-binaries.tar.gz` (archivo no versionado), verificados frente a sus originales; las fuentes siguen localmente en `mc-aot/examples` (generadas, no versionadas). Se restauran con `tar -xzf analysis/generated-examples-binaries.tar.gz -C mc-aot` o se regeneran con `bash mc-aot/build-examples.sh`. Son ejemplos, no un servidor. Ver `analysis/generated-examples-note.md`.
