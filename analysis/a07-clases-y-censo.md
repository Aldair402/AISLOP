# Frente A: clases adicionales y límites del censo

Se ejecutaron las declaraciones de instancia completas, incluido el constructor,
para estas clases del JAR vanilla 26.3:

- `net/minecraft/commands/arguments/selector/options/SetOnceOptionState`:
  constructor y `canParse`/`markParsed`.
- `net/minecraft/world/level/block/entity/BeaconBeamOwner$Section`: constructor y
  `increaseHeight`/`getColor`/`getHeight`.

`mc-aot/tests/check-vanilla-two-more-classes.py` compila cada clase a un binario
nativo, ejecuta 50 secuencias deterministas de 25 llamadas por clase y compara
cada salida con Java 25 sobre el JAR oficial. El binario se ejecuta con `PATH`
sin Java. Los casos incluyen colores negativos y extremos de `int`. La prueba
cubre esas secuencias, no demuestra equivalencia para todas las entradas ni el
arranque del servidor. Junto a `TickThrottler`, hay **tres clases con evidencia
individual de constructor y métodos declarados** bajo este perfil restringido;
no debe confundirse con 3.881 clases completas verificadas.

## Evitar una falsa admisión

La sonda encontró que `BlockUtil$IntBounds.toString()` producía Rust inválido:
el driver intentaba imprimir una referencia como entero. Ahora los descriptores
con argumentos o retornos de referencia se rechazan explícitamente en la admisión;
no se afirman como implementados. `check-class-demo-signatures.py` cubre String,
objetos, arrays, una clase primitiva positiva y la igualdad del código fuente
emitido por los dos comandos. Las dos pruebas nuevas están registradas en la
integral. Su ejecución aislada pasó; el resultado de la integral debe consultarse
por separado en `analysis/full-regressions-a07-signatures.log`.

## Sonda de generación

`class-demo-rs` ejecuta el mismo generador y guardas que `class-demo`, pero no
invoca rustc. `tools/execution-census.py` lo aplica al JAR y anota hashes del JAR
 y del compilador. Un resultado positivo solo dice que se emitió Rust; **no**
certifica que compile, ejecute o coincida con Java. Los motivos de rechazo son
el primer bloqueo observado, no una lista exhaustiva, y los 7.762 archivos
incluyen `package-info`. El censo es una herramienta de priorización, no un
contador de clases completas; el artefacto es `analysis/execution-census.json`.
