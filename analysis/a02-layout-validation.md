# A-02: layouts de grafo generados desde classfiles (experimental)

**Estado:** avance parcial del frente A. No cierra A-02 ni A-01, no conecta `Main` y no certifica clases.

## Qué se añadió

- `mc-aot/tools/numeric_bridge_layout.py`: valida un JAR **no** multi-release por SHA-256, usa `mc-aot inspect` sobre ese mismo archivo y produce un layout JSON/Rust solo si se cumple un perfil conservador: 64 clases como máximo, clase **de tipo cerrado** (o `final`, o sin subclases en el propio JAR, y se anota cuál de las dos: `closed_by`) directa de `java/lang/Object`, sin interfaces, sin `<clinit>`, sin campos estáticos/`volatile`, `int` no `final` y referencias `final` a clases `net/minecraft/...` validadas de forma recursiva. Descriptores distintos de `I`/referencia se rechazan; `int final` se rechaza porque el puente actual no lo distingue. No es un verificador JVM ni sustituye al `ClassLoader`.
- `mc-aot/tests/check-numeric-bridge-layout.py`: dos layouts cíclicos, layout vacío y orden inverso; una clase no `final` **sin subclases** se acepta (tipo cerrado) y una con subclases se rechaza; 25 rechazos (clase con subclases, interfaz, herencia, estático, `<clinit>`, `int final`, `volatile`, siete descriptores primitivos, referencia mutable, array, `String`, destino inválido/ausente, hash incorrecto, JAR con entradas duplicadas y multi-release). Classfiles generados con `javac` 25.0.5.
- `check-numeric-concurrent-graph.py` ya no declara el layout a mano: lo genera con el validador a partir del mismo JAR que se traduce (hash verificado antes y después) y conserva el rechazo de un layout incorrecto. Añade autoalias y un ciclo de dos nodos registrados antes de publicar.

## Resultados

- `analysis/a02-layout-guards.log`: OK, `javac` 25.0.5; no usa el JAR oficial.
- `analysis/a02-generated-graph.log` y `analysis/a02-generated-graph-ticktask.log`: 20 rondas Java/Rust, 23 pruebas del crate concatenado, cuatro tareas `ForkJoinPool` en Rayon, `QuartPos` oficial, ejecución sin Java en `PATH`. El registro de objetos, publicación, unión de outputs y scheduling siguen siendo harness manual.
- ~~`analysis/a02-vanilla-scan.log`: 0 de 687 candidatas~~ **Corregido el 2026-11-06:** ese log tiene una sola línea, no dice de dónde salieron las 687 ni qué cláusula falló, y el número está desactualizado. La medición real sobre las 7.762 clases del JAR oficial, con la ruta del verificador, está en [`a02-vanilla-profile-census.md`](a02-vanilla-profile-census.md): **6 aceptadas** (`WaypointStyleAsset`, `Graph`, `MobEffectUtil`, `LongJumpUtil`, `NoiseRouterData$QuantizedSpaghettiRarity`, `PreparableReloadListener$StateKey`), **ninguna con campos de instancia**, y el censo explica clase por clase qué cláusula bloquea al resto. La explicación «casi todas tienen estáticos» también era falsa: los estáticos bloquean 12 clases; el muro es `final` (5.377) y la superclase (1.527).

## Regresión

`analysis/full-regressions-a02.log`: **306 etapas, exit 0**, incluidos los dos diferenciales de grafo con layout generado; `cargo test` 60 unitarias y 26 de integración. La prueba `check-numeric-bridge-layout.py` aún no está en `run-regressions.sh` (lo integra el frente C). No certifica clases ni arranque.

Nota de entorno: la primera ejecución de la integral falló en `sweep-long` porque `TMPDIR` por defecto era un `tmpfs` de ~1 GB casi lleno; con `TMPDIR=/var/tmp` terminó correctamente. No era un fallo del código, y se descartó ese intento.

## Comandos

```sh
export JAVA_HOME=/ruta/al/jdk-25
cargo build --offline --manifest-path mc-aot/Cargo.toml
python3 mc-aot/tests/check-numeric-bridge-layout.py
python3 mc-aot/tests/check-numeric-concurrent-graph.py
python3 mc-aot/tests/check-numeric-concurrent-graph.py --ticktask
python3 mc-aot/tools/numeric_bridge_layout.py ruta.jar net/minecraft/paquete/Clase \
  --compiler mc-aot/target/debug/mc-aot --jar-sha256 <sha256> --format rust
```

## Límites

- Solo layouts de instancia en el perfil indicado; no analiza bytecode de métodos, ni `final`/`volatile` de la semántica Java, ni accesibilidad/reflexión.
- No genera registro ni publicación automáticos, no comparte estáticos ni clases y no traduce la llamada Java que uniría los backends (A-03/A-06).
- El validador no demuestra que el classfile sea correcto frente a la JVM: es una comprobación estructural y de hash.
- El probe de `Main` no se repitió; el bloqueo conocido en `new ForkJoinPool` sigue vigente.
