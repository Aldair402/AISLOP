# A-04, primer subperfil: referencias mutables entre backends (experimental)

**Estado:** subperfil parcial de A-04. No cierra A-04, no conecta `Main`, no certifica clases. **0 clases completas.**

## Qué se puede hacer ahora (y solo con opt-in del validador)

- El layout distingue `NumericGraphSlot::Ref` (campo `final`, solo lectura) de `NumericGraphSlot::MutRef` (campo no `final`, escribible). El validador `numeric_bridge_layout.py` solo emite `mutref` con `--allow-mutable-refs`; sin esa bandera sigue rechazando `referencia no final`, como hasta ahora.
- `ExternalObject::write` acepta en un slot `MutRef` un `Ref(None)` o un `Ref(Some(destino))` **ya publicado en la misma sesión y de la clase que declara el layout**. Cualquier otro destino se rechaza (`grafo: destino no registrado o incompatible`), igual que un tipo cruzado (`int` en slot de referencia o al revés).
- La escritura ocurre bajo el mutex de campos del objeto compartido, el mismo que usa el bytecode numérico en `object_store`; no hay un segundo candado ni se retiene el mutex de la tabla del `SharedHeap` durante la operación.
- Un slot `Ref` sigue rechazando escrituras (`grafo: escritura de referencia no soportada`) aunque el valor sea el mismo objeto.

## Prueba

`mc-aot/tests/check-numeric-mutable-refs.py` → `analysis/a04-mutable-refs.log`:

- `Node` sigue con `int value; final Node next;` (lectura compartida, escritura rechazada).
- `Holder` tiene `int value; Node link;` y se publica automáticamente; el diferencial escribe `link` con el mismo destino, con `null`, lo restaura, y comprueba destino no publicado, `Holder` como destino de un campo `Node` y tipos cruzados.
- El bytecode numérico traducido (`relink`) escribe `holder.link` sobre el objeto compartido.
- Cuatro tareas `ForkJoinPool` en Rayon actualizan `child` con `QuartPos` oficial; 20 rondas Java/Rust con valores idénticos y ejecución nativa sin Java en `PATH`.

## Regresión

`analysis/a04-mutable-refs.log` (nuevo diferencial) y `analysis/a04-{auto-publish,graph,graph-ticktask,bridge,layout-guards,cargo-test}.log` reejecutados tras el cambio. Integral completa: `analysis/full-regressions-a04.log`, **306 etapas, exit 0**, `cargo test` 60 + 26. Las pruebas nuevas aún no están en `run-regressions.sh` (las integra el frente C).

## Bloqueo declarado para B (no lo resuelvo en el frente A)

El compilador del backend concurrente rechaza **cualquier** campo no `final` de una clase de proyecto: `concurrent_compile.rs` → `concurrent-int: captura de referencia debe ser final: <clase>.<campo>`. Por eso el fixture concurrente aún **solo lee** `Node.next`; escribir una referencia desde bytecode concurrente requiere que B relaje esa comprobación (opt-in, p. ej. `MC_AOT_RAYON_MUTABLE_REFS=1`) y añada su propio diferencial. No lo cambié unilateralmente porque el archivo es del frente B y porque abre preguntas de semántica (visibilidad, publicación y carreras) que deben acordarse.

## Límites que siguen en pie

- Nada de arrays, `String`, subtipos, campos de tipo primitivo distinto de `int`, estáticos compartidos ni `<clinit>` concurrente.
- Sin GC ni reutilización de índices; cerrar la sesión deja de publicar pero no libera objetos.
- El mutex de campos no es el modelo de memoria JVM: no hay `volatile`, ni barreras más allá del mutex, ni garantías de orden entre objetos distintos.
- La unión de los dos programas, el `SharedHeap` y el scheduling siguen siendo harness; `Main` sigue detenido en `new ForkJoinPool`.

## Reproducir

```sh
export JAVA_HOME=/ruta/al/jdk-25 TMPDIR=/var/tmp
python3 mc-aot/tests/check-numeric-mutable-refs.py
python3 mc-aot/tools/numeric_bridge_layout.py ruta.jar net/minecraft/paquete/Clase \
  --compiler mc-aot/target/debug/mc-aot --jar-sha256 <sha256> --allow-mutable-refs --format rust
```
