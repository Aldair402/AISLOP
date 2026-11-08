# Tres records vanilla integrales: todas sus declaraciones

El backend admite los wrappers estándar de `ObjectMethods` para `equals`,
`hashCode` y `toString` de records con componentes `Z/B/C/S/I/J`. Valida el
bootstrap, clase, componentes y getters, y además el bytecode exacto del método
de instancia declarado: no sustituye un `invokedynamic` arbitrario por un
wrapper. Los componentes `float`, `double`, arrays y referencias siguen fuera;
se rechazan. El nombre sencillo de una clase anidada se obtiene de `InnerClasses`,
no cortando el nombre por `$`: se verifica también un record de nivel superior
cuyo nombre contiene `$`. `toString` se conserva como unidades UTF-16.

El driver `class-demo` admite records finales con atributo `Record`: `new` crea
y selecciona un objeto, `select @N` cambia el actual, y `equals` recibe `null` o
`@N` de objetos previamente construidos. Es un driver restringido, no una API
completa de referencias Java. El test negativo comprueba referencias e índices
inválidos. Otros argumentos de referencia siguen rechazados.

`check-vanilla-record-classes.py` compila **todas las declaraciones** y compara
constructor, lectura de campos, accessors, `equals`, `hashCode` y `toString`
con Java 25 sobre el JAR oficial; cada nativo corre sin Java en PATH. Comprueba
la superficie reflejada para detectar métodos o campos adicionales:

| Clase | Objetos | Pasos diferenciales |
|---|---:|---:|
| `net/minecraft/network/protocol/game/VecDelta$Stepped$DeltaStep` | 40 | 677 |
| `net/minecraft/server/jsonrpc/IncomingRpcMethod$Attributes` | 40 | 597 |
| `net/minecraft/server/jsonrpc/OutgoingRpcMethod$Attributes` | 40 | 517 |

Se prueban identidad, igualdad entre objetos diferentes, diferencias de campos,
`null`, límites de `short`/`int` y `select`. Fixtures adicionales incluyen
record vacío, tipos integrales completos, límites de `long`, `char` con sustituto
UTF-16 aislado y nombre de clase con `$`. `check-record-equals.py` compara 127
casos incluyendo tipos distintos; `check-record-hash.py` compara 104 y rechaza
bootstrap y cuerpo manipulados. El perfil diferencial no demuestra equivalencia
para todas las entradas ni acceso Java general.

El censo de generación (`analysis/execution-census-a12.{json,log}`) terminó con
13 de 7.762 entradas que generan Rust y 7.749 bloqueadas; las tres nuevas son
las de la tabla. **Generar Rust no es probar ejecución**; aquí existen pruebas
individuales para las 13, de las cuales seis tienen solo constructor. Esto no
certifica el servidor ni cumple el objetivo de 3.881. La tanda dirigida de diez
pruebas y `cargo test` (33/33) pasaron. Ambas pruebas nuevas están en la integral;
la integral completa sigue pendiente y no se declara verde.
