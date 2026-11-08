# Censo de generación de clases completas: ejecución en lote

Para evitar repetir la indexación del JAR por cada clase, `class-demo-scan`
reutiliza el índice del classpath dentro de cada proceso y aplica a cada entrada
la misma función `compile_class_demo` de `class-demo-rs`. El resultado contiene
una fila por clase, con errores codificados en UTF-8 hexadecimal. El consumidor
verifica número, índice y orden de filas; un proceso fallido o un informe
incompleto aborta el censo, no se cuenta como una clase bloqueada. Se mantiene
`--individual` como referencia. Esto genera Rust **sin invocar rustc ni ejecutar**
el resultado; no mide comportamiento ni arranque.

La prueba `check-class-demo-signatures.py` contrasta ambos modos sobre fixtures,
incluida una entrada repetida. `check-execution-census-batch.py` compara 33
clases del JAR oficial, incluidas las dos anclas positivas y un bloqueo real.
Ambas pasaron por separado. También se comparó una muestra reproducible de 123
clases oficiales con `Random(905)`: **0 discrepancias**; en esa ejecución el
lote tardó 2,8 s y los procesos individuales 35,2 s (solo la fase de traducción;
no es una promesa de rendimiento para otras máquinas).

## Resultado obtenido

JAR interior oficial 26.3, SHA-256
`a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6`:

- 7.762 entradas de clase procesadas; incluyen 326 `package-info`.
- 10 generan Rust con el perfil de clase actual; 7.752 se detienen en el primer
  bloqueo. **La generación no verifica que ese Rust compile ni su equivalencia.**
- Las 10 son las clases con pruebas individuales registradas previamente: seis
  solo tienen constructor. Esas pruebas son diferenciales en entradas concretas,
  no una demostración exhaustiva de equivalencia.
- Primer bloqueo por clase, no todos los bloqueos: base no admitida 3.085;
  interfaz/abstracta/enum 1.422; clase no pública 1.351; interfaces 540;
  `<clinit>` 514; ruta inválida 326. Entre las 3.085 bases rechazadas hay
  1.313 `java/lang/Record`; no se afirma que quitar ese solo bloqueo admita
  todas esas clases.

El JSON `analysis/execution-census.json` conserva clases, motivos normalizados y
hashes de JAR y binario traductor; el log `analysis/execution-census-full.log`
registra `CENSO_RC=0`. La integral que incluye la prueba de lote sigue pendiente
hasta completar toda la ejecución con el árbol final. La meta de 3.881 y el
arranque del servidor siguen abiertos.

## Siguiente corte: records primitivos

De esas 1.313 entradas cuya primera causa es `java/lang/Record`, 12 son
layouts describibles con únicamente campos primitivos y sin los bloqueos de
estáticos/`<clinit>`/interfaces anotados por el censo de layouts. **No son 12
clases listas**: ese censo no examina todas las firmas ni los bytecodes de sus
métodos. Por ejemplo, `FileSystemCapabilities` tiene retorno de array, y
`FpsStat` tiene un método estático; ambos incluyen `equals`, `hashCode` y
`toString` generados mediante `invokedynamic`/`ObjectMethods`. Para admitirlos
harían falta, además de `Record.<init>`, traducción de esas operaciones y del
driver de referencias, con pruebas diferenciales; no se deben saltar métodos.
