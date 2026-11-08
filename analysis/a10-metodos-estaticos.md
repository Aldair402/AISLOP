# Métodos estáticos en el driver de clase

El perfil `class-demo` ya no rechaza una clase únicamente por declarar métodos
estáticos: compila todas sus declaraciones admitidas, tanto estáticas como de
instancia. Un paso estático puede ejecutarse antes de `new`; el de instancia
sigue exigiendo un objeto. Se inicia la clase al invocar estáticos y se preparan
las ranuras estáticas de las dependencias descubiertas antes de sus `<clinit>`.
La clase raíz todavía rechaza campos estáticos y `<clinit>`, por lo que esto no
es soporte general de inicialización de clases.

La prueba `check-class-demo-static-methods.py` compara 108 pasos con Java 25:
métodos estáticos e instancia, llamadas antes y después de crear objeto,
`int`/`long` con desbordamiento, `float`, retorno `String` y una dependencia
con campo estático mutable e inicializador. El binario se ejecuta sin Java en
PATH. La prueba también rechaza `<clinit>` en la raíz, sobrecargas, firmas con
referencias, nombres reservados por el driver y constructores con manejadores.

La prueba de dependencia descubrió un fallo real: el heap de `class-demo` no
reservaba las ranuras de estáticos de dependencias y fallaba por índice fuera de
rango. Ahora las prepara con los valores del grafo antes de inicializar clases;
el caso se ha añadido como regresión. También se cierra la omisión de validación
de manejadores en constructores y se rechaza el nombre `read`, reservado por el
protocolo, en vez de generar una rama inalcanzable.

## Resultado en el JAR oficial

Censo por lotes con la versión nueva: **7.762 entradas, 10 generan Rust**,
igual que antes; los diagnósticos de las 158 clases que antes se detenían en
método estático cambian a sus siguientes bloqueos. Generar Rust no equivale a
compilarlo ni probarlo. `net/minecraft/util/Ease` ya supera ese bloqueo, pero
con el bundle oficial se detiene en `Mth.<clinit>` → `Util.<clinit>` →
`ForkJoinPool`; no se cuenta como clase completa.

El censo está en `analysis/execution-census-a10.json` y su log con `CENSO_RC=0`
en `analysis/execution-census-a10.log`. Las pruebas mencionadas y `cargo test`
(33/33) pasaron aisladamente. Están registradas en la integral, cuyo resultado
completo permanece pendiente. No se declara servidor arrancado ni 3.881 clases.
