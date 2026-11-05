# A-02: layouts de grafo generados desde classfiles (experimental)

**Estado:** avance parcial del frente A. No cierra A-02 ni A-01, no conecta `Main` y no certifica clases.

## Qué se añadió

- `mc-aot/tools/numeric_bridge_layout.py`: valida un JAR **no** multi-release por SHA-256, usa `mc-aot inspect` sobre ese mismo archivo y produce un layout JSON/Rust solo si se cumple un perfil conservador: 64 clases como máximo, clase `final` directa de `java/lang/Object`, sin interfaces, sin `<clinit>`, sin campos estáticos/`volatile`, `int` no `final` y referencias `final` a clases `net/minecraft/...` validadas de forma recursiva. Descriptores distintos de `I`/referencia se rechazan; `int final` se rechaza porque el puente actual no lo distingue. No es un verificador JVM ni sustituye al `ClassLoader`.
- `mc-aot/tests/check-numeric-bridge-layout.py`: dos layouts cíclicos, layout vacío y orden inverso; 26 rechazos (clase no final, interfaz, herencia, estático, `<clinit>`, `int final`, `volatile`, siete descriptores primitivos, referencia mutable, array, `String`, destino inválido/ausente, hash incorrecto, JAR con entradas duplicadas y multi-release). Classfiles generados con `javac` 25.0.5.
- `check-numeric-concurrent-graph.py` ya no declara el layout a mano: lo genera con el validador a partir del mismo JAR que se traduce (hash verificado antes y después) y conserva el rechazo de un layout incorrecto. Añade autoalias y un ciclo de dos nodos registrados antes de publicar.

## Resultados

- `analysis/a02-layout-guards.log`: OK, `javac` 25.0.5; no usa el JAR oficial.
- `analysis/a02-generated-graph.log` y `analysis/a02-generated-graph-ticktask.log`: 20 rondas Java/Rust, 23 pruebas del crate concatenado, cuatro tareas `ForkJoinPool` en Rayon, `QuartPos` oficial, ejecución sin Java en `PATH`. El registro de objetos, publicación, unión de outputs y scheduling siguen siendo harness manual.
- `analysis/a02-vanilla-scan.log`: de 687 clases candidatas del índice estático (`final`? filtro previo por superclase/interfaces/campos), **0** aceptadas por el perfil. Es esperado: casi todas tienen estáticos o no son `final`; no existe todavía un objeto vanilla válido para el grafo, y este barrido no certifica nada.

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
