# Records: metadatos y `hashCode` integral

El parser lee ahora el atributo `Record` en orden, distingue un record vacío de
una clase sin el atributo y conserva nombres y descriptores de componentes. El
comando `inspect-record` expone esa superficie estructural. No valida toda la
clase ni demuestra que sea ejecutable. La prueba `check-record-metadata.py`
compara componentes y orden con reflexión Java 25 para siete clases reales y
sintéticas; comprueba anotaciones de componente, record vacío y no-record, y
rechaza atributo duplicado, descriptor inválido y archivo truncado.

El backend numérico reconoce `java/lang/runtime/ObjectMethods.bootstrap` para
**solo `hashCode` de records cuyos componentes son `boolean`, `byte`, `char`,
`short`, `int` o `long`**. Antes de emitirlo valida el propietario, descriptor,
clase del record, atributo y nombres de componentes, y cada `REF_getField` con
su campo final de instancia y descriptor. No acepta `invokedynamic` arbitrario
como si fuera este bootstrap. La mezcla usa multiplicación de 31 con desbordamiento
Java, hash de boolean y XOR de las dos mitades de long.

`check-record-hash.py` traduce código que construye records y ejecuta `hashCode`:
104 casos con Java 25, incluido el record vanilla
`net/minecraft/network/protocol/game/VecDelta$Stepped$DeltaStep`, coinciden con
el binario nativo sin Java en PATH. Incluye record vacío, límites numéricos y
casos aleatorios. Una receta de bootstrap manipulada se rechaza, al igual que
`equals`, `toString` y componentes `float`, que aún no están implementados en
este perfil. **Esto es evidencia de un método de DeltaStep, no de la clase entera.**

Pasaron aisladamente ambas pruebas, el test de estáticos, `cargo test` (33/33) y
la tanda dirigida de ranuras, F/D, `IntBounds` y censo lote/individual. La
integral completa se lanzó, pero no se declara verde hasta su resultado final.
El censo en `analysis/execution-census-a11-final.{json,log}` procesó 7.762
entradas y sigue en 10 generadoras de Rust; es idéntico en resultados al censo
A-10 y no significa clases completas ni arranque. Sigue pendiente implementar
`equals`/`toString`, referencias del driver y verificar todas las declaraciones
antes de contar un record como clase completa.
