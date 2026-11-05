# TODO compartido — Minecraft JAR → binario nativo

Este documento propone cómo repartir el trabajo entre **al menos tres personas**, sin asignar nombres ni dar por hecho que alguien ya tomó una tarea. Es una guía operativa complementaria a [`ROADMAP.md`](ROADMAP.md), que sigue definiendo el objetivo y los criterios de validación.

## 1. Punto de partida

**Base observada: commit `8fa1893`.** Actualizar esta sección cuando cambie el estado, con enlaces a la evidencia correspondiente.

- Objetivo: JAR oficial del servidor → ejecutable nativo sin JVM externa, con arranque real y **3.881 de 7.762 clases completas verificadas**. Se prioriza lo que Minecraft usa, no compatibilidad Java general.
- **0 clases completas certificadas.** El indexado y los métodos que pasan pruebas no cuentan como clases completas.
- **No hay servidor nativo arrancable.** El probe de `Main` se detiene al compilar `new ForkJoinPool` en `Util.makeExecutor`: [`analysis/main-completed-future-attempt.log`](analysis/main-completed-future-attempt.log).
- Existen dos backends experimentales y puentes opt-in, pero su composición, registro y publicación son manuales en las pruebas; no están conectados automáticamente a `Main`.
- `completedFuture` está limitado a futuros ya completados normalmente. No hay implementación general de futuros pendientes, composición, cancelación o excepciones.
- Última integral aprobada en esa base: **306 etapas**, exit 0; [`analysis/full-regressions-completed-future.log`](analysis/full-regressions-completed-future.log). Una suite nueva no cuenta como aprobada hasta terminar correctamente.
- **`log4rs` está aparcado** por decisión del proyecto. El logging sigue siendo necesario para un arranque real: no sustituirlo por silencios o stubs en una ruta que se declare funcional. Los stubs sí se pueden usar en pruebas aisladas si se identifican.

## 2. Cómo tomar trabajo sin duplicarlo

1. **Elegir una tarea por su ID** (`A-01`, `B-01`…) y buscar antes si ya hay una issue o PR abierta con ese ID. Si no existe, crearla o acordarlo en el canal del equipo; indicar alcance, archivos previstos y responsable. No inventamos responsables en este archivo.
2. Mantener **una persona responsable por tarea** y, de ser posible, otra revisora. Una persona puede tomar varias tareas pequeñas; una tarea grande puede dividirse en subissues con fronteras claras.
3. Usar estados: `disponible`, `en curso`, `bloqueada` (con dependencia y motivo), `en revisión` o `terminada` (con PR y evidencia). Las casillas de abajo describen el trabajo pendiente; no son un sistema de reservas en tiempo real. **Las issues/PR del equipo son la fuente de verdad para reservas**. Si no usan issues, acuerden un tablero equivalente antes de empezar.
4. Crear una rama por tarea desde `main` actualizado, por ejemplo `trabajo/a-01-contrato-heap`. Abrir un **borrador de PR temprano** con el ID y los archivos afectados. Evitar pushes directos a `main`; pedir revisión cruzada cuando sea posible.
5. Si dos tareas necesitan el mismo archivo o contrato, avisar antes de editarlo. La tabla siguiente asigna una frontera inicial; no es una prohibición permanente ni sustituye la revisión. Para cambios compartidos, hacer primero un PR pequeño de interfaz, acordar orden de integración y actualizar las ramas dependientes.
6. Al terminar, enlazar el PR, pruebas y limitaciones en la issue; marcar aquí la casilla solo cuando se haya integrado y verificado. Un diagnóstico, un prototipo, un fixture con stubs o un método aislado **no** cierran una tarea que exige integración real.

### Reparto inicial sugerido

| Frente disponible | Responsabilidad inicial | Archivos principales | Primera tarea en paralelo |
|---|---|---|---|
| **A — Backend principal e integración** | Heap numérico, representación compartida y unión automática con las llamadas Java del backend principal. | `mc-aot/src/numeric.rs`, `numeric_runtime.inc`, `numeric_concurrent_bridge.inc`, `numeric_concurrent_graph_bridge.inc`. | **A-01** |
| **B — Concurrencia y futures** | Contratos del backend concurrente, Rayon, lifecycle, errores y futures. | `mc-aot/src/concurrent_heap.rs`, `concurrent_compile.rs`, `executor_runtime.rs`, `frame_vm.rs`, `rayon_scheduler.rs`, `scheduler.rs`. | **B-01** |
| **C — Evidencia, clases y reproducibilidad** | Pruebas diferenciales, inventario/certificación de clases, probes y coordinación de la suite. | `mc-aot/tools/class-surface-evidence.py`, herramientas de inventario, `mc-aot/run-regressions.sh`, informes en `analysis/`. | **C-01** |

**Fronteras para evitar choques:**

- A propone los cambios de API necesarios en `concurrent_heap.rs`; B los implementa o coordina un PR conjunto. B propone los cambios necesarios en `numeric.rs`/`numeric_runtime.inc`; A los integra. No crear dos representaciones incompatibles por separado.
- `mc-aot/src/main.rs`, `Cargo.toml`, `Cargo.lock` y las firmas usadas por ambos backends son **compartidos**: anunciar en la issue qué líneas/contratos se van a cambiar y acordar un único PR de integración.
- Cada frente crea pruebas con nombres nuevos para su tarea. Para modificar una prueba existente de otro frente, coordinarse con su responsable. **C integra entradas en `run-regressions.sh`** después de que A/B indiquen el comando y las dependencias; los autores conservan la responsabilidad de sus pruebas.
- Cada persona trabaja en un clon o worktree separado. La suite escribe `analysis/*-latest.log` y genera `mc-aot/examples/`: **no ejecutar dos integrales simultáneas en el mismo árbol**. No incluir en un PR los cientos de logs ajenos que cambien por una ejecución; conservar el log relevante con nombre inequívoco y el resumen de versiones.
- `ROADMAP.md`, `README.md` y este TODO también son compartidos: actualizaciones pequeñas, vinculadas a resultados verificables y coordinadas por la persona que integra la tarea.

## 3. Frente A — Backend principal y unión de heaps

**No depende de terminar B-01 para empezar A-01/A-02.** Leer primero [`analysis/heap-bridge-design.md`](analysis/heap-bridge-design.md) y [`analysis/next-numeric-concurrency-integration.md`](analysis/next-numeric-concurrency-integration.md).

- [ ] **A-01 · Contrato de integración** — Definir en un documento corto identidad, propiedad, vida de objetos, layouts y pertenencia a heap; decidir cómo se transfieren referencias y cómo se libera cada lock. Enumerar explícitamente lo que queda rechazado. **Termina cuando** A y B revisan un contrato con casos de alias, heap ajeno, sesión cerrada, ciclos y orden de locks; no requiere cambiar el runtime.
- [ ] **A-02 · Generación/verificación de layouts** — Pasar de layouts escritos a mano en el harness a una selección verificada contra el classfile para un perfil acotado. Distinguir `int` de `byte`/`char`/`short`/`boolean`, referencias finales y clases exactas. **Termina cuando** bytecode válido se acepta y hashes/tipos/flags/layouts alterados se rechazan en pruebas; sin afirmar soporte de todos los objetos.
- [ ] **A-03 · Identidad y publicación automática** — Generar el registro/publicación de los objetos admitidos desde una ruta traducida del backend principal, sin copiar campos ni registrar manualmente cada instancia en Rust. **Depende de A-01/A-02 y del contrato de B.** Comparar alias, null, referencias ajenas, doble registro y cierre de sesión frente a la conducta definida; rechazar lo que aún no se modele.
- [ ] **A-04 · Referencias y mutación** — Ampliar de forma incremental el puente más allá de referencias finales de solo lectura: evaluar escrituras, ciclos, alias y publicación. Primero fijar semántica y sincronización con B; arrays, cadenas, subtipos y vida/GC no se dan por implementados. **Termina por subperfil** con diferenciales y guardas, no con un booleano «heap completo».
- [ ] **A-05 · Monitores e inicialización de clases** — Compartir monitor reentrante y establecer una política común de estáticos e inicialización perezosa, reentrada, espera y fallos. Probar que no se mantiene un lock global al esperar ni al invocar callbacks. Si `wait`/`notify` o interrupción no se implementan, rechazarlos explícitamente.
- [ ] **A-06 · Entrada Java integrada** — Crear un fixture cuya llamada Java en el backend principal publique un objeto, cree/envíe tareas y observe el estado tras `join`, **sin que el harness una los outputs ni programe las tareas manualmente**. **Depende de A-03/A-05 y del executor acordado con B.** Validar contra Java 25 con alias, reentrada, overflow, errores y binario sin Java en PATH.
- [ ] **A-07 · Ruta real hacia `Util.makeExecutor`** — Conectar progresivamente la llamada real desde el backend principal al adaptador revisado: constructor de cuatro argumentos, factory/handler, `TracingExecutor` y cierre pertinente. **Depende de A-06 y del contrato/lifecycle de B-02, B-06 y B-07.** Mantener una guarda donde falte comportamiento; no simular logger o callbacks.
- [ ] **A-08 · Repetir probe de Main** — Tras A-07, compilar desde el bundle oficial, registrar primer bloqueo, flags, hash, exit code y ausencia o presencia real del binario. Borrar el binario previo antes del intento. Un nuevo bloqueo es un resultado válido; compilar no significa arrancar.

## 4. Frente B — ForkJoinPool, workers y futures

Leer [`mc-aot/src/executor_runtime.rs`](mc-aot/src/executor_runtime.rs), [`mc-aot/src/concurrent_compile.rs`](mc-aot/src/concurrent_compile.rs) y los oráculos de `analysis/`. Estos perfiles están aislados del backend principal hasta que A los conecte.

- [ ] **B-01 · Convertir oráculos en contrato comprobable** — Partir de `check-completable-future-oracle.py` y `check-forkjoin-handler-oracle.py`. Documentar qué casos son Java solamente, qué ya tiene diferencial nativo y cuáles faltan. Añadir la prueba de handler a la suite mediante C. **Termina cuando** el contrato distingue `execute`, `submit`, `join`, `get`, handler, cierre y excepciones sin afirmar equivalencia aún no probada. **Estado:** entregado — 83 casos, 3 oráculos Java a 40 rondas, verificador y documento regenerados desde el JSON; falta la confirmación de C para la suite.
- [ ] **B-02 · Lifecycle del pool** — Ampliar el perfil restringido con pruebas de fábrica, inicio/terminación de workers, rechazo tras cierre y esperas. Cubrir el constructor de cuatro argumentos sin prometer orden global de tareas ni lifecycle JVM completo. Rechazar handlers o configuraciones no implementadas. **Estado:** entregado — `isShutdown`/`isTerminated`/`parallelism` con 24 resultados diferenciales contra Java 25 y prueba de crate; el constructor de cuatro argumentos con factory depende de B-06.
- [ ] **B-03 · Modelo de futuros pendientes** — Diseñar estado y publicación para pendiente/completado normal/fallido/cancelado, identidad, espera y finalización única. Empezar en el backend concurrente; conservar el perfil de `completedFuture` existente. **Termina por subperfil** con estados, transiciones y carreras comparados contra Java, y guardas para los demás. **Estado:** en curso — primer subperfil integrado (pendiente → completado normal, publicación en campo final, finalización única) con 48 resultados Java 25 en `check-rayon-pending-future.py` y tres pruebas del heap/runtime; siguen rechazados fallo, cancelación efectiva y espera.
- [ ] **B-04 · `get`/`join` y fallos observables** — Distinguir terminación normal, `ExecutionException`/`CompletionException`, cancelación, timeout e interrupción donde se implementen; no convertir panics o límites Rust en excepciones Java equivalentes. Si falta un caso, abortar explícitamente. **Depende del contrato B-03 y del modelo de excepciones acordado con A.**
- [ ] **B-05 · Envío y composición necesarios para Minecraft** — Priorizar `supplyAsync`, `thenApply`, `thenCompose`, `allOf` y callbacks con executor según las rutas comprobadas. Probar ejecución del callback, identidad, errores y rechazo sin asumir orden no garantizado. **Depende de B-03/B-04**; dividir por método si hace falta.
- [ ] **B-06 · Factory y handler de `Util`** — Investigar y traducir/adaptar los callbacks y nombres reales de workers de `Util.makeExecutor`, incluidos efectos observables de `Util.onThreadException`. Registrar los bloqueos de logger y `CrashReport`; no sustituirlos silenciosamente. **Depende de B-02/B-04**, y de una solución acordada para las dependencias necesarias. **Estado:** bloqueada con causa documentada — [`analysis/b06-util-factory-blockers.md`](analysis/b06-util-factory-blockers.md) caracteriza la factory real (`Util$2 extends ForkJoinWorkerThread`, `onStart` con Tracy, `onTermination` con slf4j) y propone dos pasos; no se implementa nada hasta que se decida el backend de logging y se cierre B-04.
- [ ] **B-07 · Interfaz para A** — Entregar una API estable documentada para crear/enviar/esperar/cerrar y transportar referencias, con reglas de ownership, locks, fallos y clases admitidas. Añadir tests de frontera y coordinar el PR compartido; A consume la interfaz sin duplicar el scheduler. **Estado:** en revisión — superficie, propiedad, locks, fallos, clases admitidas y opt-ins documentados en [`analysis/b-api-for-a.md`](analysis/b-api-for-a.md), con seis pruebas de frontera en `mc-aot/tests/rayon_b_api.rs`; quedan abiertas las decisiones de excepciones, `commonPool()` y opt-in único con A.
- [ ] **B-08 · Estrés y regresiones concurrentes** — Añadir repeticiones para publicación, alias, reentrada, races de finalización y cierre. Comparar **invariantes**, no órdenes no garantizados; incluir timeouts para detectar bloqueos. Pedir a C la incorporación en la integral. **Estado:** entregado — cinco pruebas de invariantes con perro guardián, verdes en `cargo test` y en la integral (exit 0, 310 etapas); falta la confirmación de C para la integral.
- [ ] **B-09 · Referencias mutables en el backend concurrente** — Admitir campos de referencia no `final` bajo `MC_AOT_RAYON_MUTABLE_REFS=1`, escribiendo a través del mutex de campos con la regla de destino publicado y clase esperada, orden campos→monitor, y sin reclamar el modelo de memoria de Java. Mantener el rechazo literal sin el opt-in; casos de contrato, prueba de estrés y diferencia declarada en `b-api-for-a.md`. **Depende de A-04; acordado con A en `Q-AB-1`.** **Estado:** entregado — `MC_AOT_RAYON_MUTABLE_REFS=1` admite campos de referencia no `final` (escritura por el mutex del heap, destino comprobado, `final` sigue cerrado), con 84 resultados diferenciales contra Java 25, guarda sin opt-in y prueba de reenlazado bajo monitor (20×4×100, sin nodos perdidos ni ciclos). Falta la revisión de C y la confirmación de A del orden campos→monitor.

## 5. Frente C — Calidad, clases y arranque reproducible

Este frente puede avanzar desde el primer día; no necesita esperar a que `Main` funcione. Colaborar con A/B en las pruebas de frontera sin modificar sus módulos sin acuerdo.

- [ ] **C-01 · Línea base para colaboradores** — En un clon limpio, seguir la preparación del README, verificar hashes del bundle/JAR interno y registrar Rust, JDK 25, sistema, comandos y primer fallo. Ejecutar pruebas focalizadas y `cargo test`; documentar si la integral tarda o falla, sin copiar el resultado de otra máquina como propio.
- [ ] **C-02 · Inventario y contador verificable** — Diseñar un registro que distinga `inventariada`, `evidencia parcial`, `pendiente de revisión` y `completa`. Cada clase debe estar ligada al hash del JAR y classfile, superficie completa, pruebas, límites y revisión. Nunca contar automáticamente una clase por tener métodos compilados. Mantener **0** hasta que haya una clase que supere el criterio del roadmap.
- [ ] **C-03 · Primer candidato a clase completa** — Revisar `QuartPos` o seleccionar otra clase pequeña realmente utilizada; reconciliar todos sus campos, métodos, constructor, herencia e interfaces. `QuartPos` tiene evidencia parcial y su constructor privado sigue pendiente. Crear un paquete reproducible de pruebas y revisión; si hay lagunas, dejarlas explícitas y no sumar la clase.
- [ ] **C-04 · Partición por familias** — Preparar lotes sin solapamiento para coordenadas/primitivas, registries/recursos, serialización, chunks/mundo, red/protocolo y entidades. Cada lote debe listar clases/IDs, dependencias, responsable al reservarse y evidencia existente. Priorizar rutas relevantes para servidor, distinguir análisis estático de ejecución real y evitar repartir «porcentaje» sin verificar clases.
- [ ] **C-05 · Arnés diferencial** — Hacer reproducible la comparación Java/nativo: entradas, stdout/stderr, exit codes, efectos de archivo, excepciones, aleatoriedad controlada y límites; guardar hashes/configuración. Exigir que el ejecutable nativo corra sin Java en PATH. Los fixtures con stubs deben etiquetarse con precisión.
- [ ] **C-06 · Suite y automatización** — Integrar pruebas nuevas en `mc-aot/run-regressions.sh`, incluida B-01, y documentar comandos focalizados, tiempos, requisitos y logs. Explorar CI por etapas con límites de memoria/tiempo y sin subir JARs; una integral parcial o interrumpida no se presenta como aprobada. Si se agrega CI, describir qué ejecuta realmente.
- [ ] **C-07 · Probe aislado de arranque** — Mantener un guion reproducible de `Main` en directorio temporal: limpiar binarios viejos, registrar configuración y bloqueo, no aceptar EULA ni abrir puertos por defecto. Preparar, sin ejecutarlo prematuramente, el plan de creación de mundo, cliente autorizado, guardado, parada y reinicio que exige el roadmap.
- [ ] **C-08 · Integración y liberación de lotes** — Revisar PRs de A/B, resolver conflictos de interfaz con ambos responsables, correr pruebas del cambio y luego integral antes de declarar un hito. Actualizar resultados y pendientes en roadmap; dejar registrado qué commit exacto se probó.

## 6. Después de las primeras puertas

No son tareas reservadas todavía; abrirlas y dividirlas cuando se conozca el bloqueo real:

- [ ] **D-01 · Recursos y entorno** — Classpath, archivos, configuración, propiedades, locale/zona horaria y red requeridos por Minecraft, con efectos y errores contrastados.
- [ ] **D-02 · Eula real** — Continuar desde el bloqueo de `Exception.toString`; probar aceptación/rechazo y archivos con dependencias reales o adaptadores verificados. No activar aceptación por defecto.
- [ ] **D-03 · Logging real** — Solo cuando el equipo decida retomar esta puerta: evaluar la ruta Java o el adaptador Rust frente a configuración y comportamiento real. `log4rs` sigue aparcado hasta entonces; no confundir sus pruebas aisladas con compatibilidad Log4j.
- [ ] **D-04 · Primer ciclo de servidor** — Una vez compilado `Main`, arrancar sin JVM externa en entorno aislado; probar mundo, puerto local, cliente autorizado, operaciones básicas, guardado, cierre y reinicio. Guardar evidencia y no inferir rendimiento.
- [ ] **D-05 · Escalar clases completas** — Pasar por los hitos 1 → 777 → 1.941 → 3.881, verificando la superficie y comportamiento según `ROADMAP.md`. Dividir por lotes reservables y revisar cada lote; no extrapolar desde muestras.

## 7. Preparación y pruebas

Desde la raíz, seguir primero **Preparación tras clonar** en [`README.md`](README.md): los JARs oficiales y herramientas externas no se incluyen en Git. Se necesitan Rust/Cargo, Python 3 y **JDK 25** para los oráculos. Ajustar `JAVA_HOME` a la instalación local:

```sh
export JAVA_HOME=/ruta/al/jdk-25
cargo test --manifest-path mc-aot/Cargo.toml
python3 mc-aot/tests/check-numeric-concurrent-bridge.py
python3 mc-aot/tests/check-numeric-concurrent-graph.py
python3 mc-aot/tests/check-numeric-concurrent-graph.py --ticktask
python3 mc-aot/tests/check-numeric-completed-future.py
python3 mc-aot/tests/check-rayon-shared-completed-future.py
python3 mc-aot/tests/check-real-chunk-passthrough-future.py
python3 mc-aot/tests/check-class-surface-evidence.py
python3 mc-aot/tests/check-futures-contract.py
```

Esos son ejemplos de pruebas focalizadas, **no** una integral ni una lista de requisitos para cada PR. Elegir las relevantes según el cambio. Para reproducir el wrapper que evita contaminación de stdout por `hsperfdata`, ver `mc-aot/tools/java-no-perf-wrapper.sh` y ejecutarlo con `bash`. La integral es costosa:

```sh
bash mc-aot/run-regressions.sh > analysis/full-regressions-MI-TAREA.log 2>&1
```

Comprobar el **código de salida** y el final del log; no sobrescribir evidencia anterior ni llamar «aprobada» a una ejecución interrumpida. Comunicar si no se pudo completar. Antes de ejecutar un binario generado, borrar el anterior: un fallo de compilación podría dejarlo intacto.

## 8. Lista mínima para cada PR

- [ ] ID/título, responsable, alcance, archivos tocados y dependencias/PR relacionados.
- [ ] Comportamiento implementado y **lo que todavía se rechaza**; indicar opt-ins, stubs y sustitutos Rust.
- [ ] Pruebas y comandos exactos, JDK/Rust/SO, entradas, hashes relevantes, resultados y logs; Java se usa como oráculo, no como dependencia del binario final.
- [ ] Casos normales, límites, null/alias, errores y, si aplica, intercalados concurrentes o efectos de archivos. No afirmar equivalencia general a partir de una muestra.
- [ ] Cambios de contrato discutidos con el otro frente y pruebas de regresión pertinentes. Registrar si la integral está pendiente, falló o terminó con exit 0.
- [ ] Si se propone contar una clase, adjuntar la superficie completa y la evidencia/revisión exigidas en `ROADMAP.md`. Si se propone arranque, demostrar el ciclo solicitado, no solo un mensaje.
- [ ] Sin JARs oficiales, ejecutables generados, credenciales, claves privadas ni datos personales innecesarios en el commit. Cada colaborador usa su propia identidad Git y acceso; no se comparten claves privadas.

### Plantilla rápida de issue

```text
ID / título:
Responsable y revisor:
Estado: disponible | en curso | bloqueada | en revisión | terminada
Alcance y archivos reservados:
Depende de:
Resultado verificable / criterios de aceptación:
Pruebas, entorno y evidencia:
Limitaciones, decisiones y PR relacionado:
```
