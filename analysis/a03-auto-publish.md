# A-03: publicación automática de objetos desde el bytecode numérico (experimental)

**Estado:** avance del frente A, aún no cerrado. No conecta `Main`, no une estáticos, clases ni excepciones Java, y no certifica ninguna clase.

## Qué cambió

- `mc-aot/src/numeric_runtime.inc`: nueva frontera `PublishSink` con sesión por hilo (`install_publish_session`, `clear_publish_session`). En `object_new` (no en `LocalObj`) se consulta la sesión; si el sink admite la clase, el objeto se convierte en `SharedObj` **al construirse** y se entrega `(owner, índice, clase, handle)` al sink. Sin sesión instalada no se comparte nada. Publicar desde otro `Heap` numérico detiene el programa con un error explícito; una sesión doble se rechaza.
- `mc-aot/src/numeric_concurrent_graph_bridge.inc`: `NumericGraphBridge::install` instala el sink usando los layouts ya validados por classfile y `lookup` devuelve el `ObjectId` sin pasar layouts. Se conserva el `attach` manual anterior para los diferenciales previos y `NumericGraphLayout` pasa a `Copy`.
- `mc-aot/tests/check-numeric-auto-publish.py`: el `harness` ya **no enumera instancias ni layouts**: instala la sesión con el layout generado por `numeric_bridge_layout.py`, ejecuta el `<clinit>` traducido y los objetos `root`/`child` quedan publicados; también se publican los que crea después el método `fresh`. Cuatro tareas `ForkJoinPool` en Rayon actualizan el mismo objeto bajo el monitor compartido y el valor coincide con Java 25.

## Resultados

`analysis/a03-auto-publish.log`: 20 rondas Java/Rust, 20 valores comparados, guardas:
sesión duplicada rechazada, clase sin layout no compartida (`lookup` falla), cierre de sesión detiene publicaciones nuevas sin romper lo ya publicado, y el proceso hijo que publica desde otro heap termina con código 2 y `publicación: otro heap numérico`.

Diferenciales existentes reejecutados tras el cambio: `a03-graph.log`, `a03-graph-ticktask.log`, `a03-bridge.log`, `a03-completed-future.log`, `a03-layout-guards.log` y `a03-cargo-test.log`.

## Límites explícitos

- La sesión es **por hilo**; el llamador publica, los workers solo leen y navegan lo ya publicado. Un objeto creado por un worker no se publica.
- Solo objetos ordinarios del perfil de layout: sin estáticos, `<clinit>` compartido, arrays, `String`, subtipos ni escritura de referencias.
- El `SharedHeap`, los layouts y la unión de los dos programas siguen siendo los del harness; `Main` no usa esta ruta y sigue detenido en `new ForkJoinPool`.
- La publicación ocurre antes de que el constructor termine de fijar campos: es correcto porque los valores por defecto respetan el layout, pero no demuestra publicación segura de un objeto en construcción entre hilos (escape de `this`).
- Cierre de sesión no espera tareas ni define reapertura; no hay GC ni reutilización de índices.
