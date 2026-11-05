# B-10, referencias del proyecto como valor de retorno (subperfil del backend concurrente)

**Estado:** entregado y verificado en este entorno. No cierra el perfil concurrente, no conecta `Main`, no
certifica clases. **0 clases completas.**

## Qué se admite ahora (y solo con opt-in)

Con `MC_AOT_RAYON_PROJECT_REFERENCES=1` —el opt-in que ya materializaba objetos del proyecto— el generador
`concurrent-rayon-int-demo` admite además:

- **Métodos de clase del proyecto que devuelven una referencia del proyecto.** `Node step(){return next;}`
  ya compila: el `areturn` comprueba que el valor sea de la clase declarada o `null` y lo devuelve al frame
  llamador, que puede encadenar (`head.step().step()`), guardarlo en un local o pasarlo como argumento.
- **Constructores de firma mixta.** `(ILnet/minecraft/test/Node;)V` deja de ser «firma no soportada»; los
  parámetros admitidos siguen siendo `int` y referencias del proyecto, cada uno un slot.
- **Parámetros con referencia del proyecto en métodos no constructores**, con la misma regla.

Nada más cambia: siguen fuera los arrays, los tipos primitivos distintos de `int`/`long` donde ya estaban, los
`String`, los subtipos, las interfaces, la jerarquía abierta, `<clinit>` y las excepciones Java.

## Por qué existía la brecha

B-09 la encontró y la declaró en vez de taparla: su propio fixture tuvo que leer `a.next` porque
`Node step()` se rechazaba con `concurrent-int: areturn no soportado`. Un perfil que puede leer un campo de
referencia pero no puede llamar a un método que lo devuelve obliga a reescribir el Java que se quiera traducir,
y eso es exactamente lo que este proyecto no hace.

## La comprobación de clase del retorno

El `areturn` traducido compara `heap.class_of(id)` con la clase exacta del descriptor. Es **defensa**, no un
camino probado: desde fuente Java type-safe `javac` no permite devolver un `Leaf` donde se declara `Node`, así que
la rama de rechazo no se puede disparar sin bytecode manipulado. Se declara así en el contrato
(`refs.return-exact-class`) y **no** se cuenta como cobertura de un error real.

## Prueba

`mc-aot/tests/check-rayon-project-ref-returns.py` → `analysis/check-rayon-project-ref-returns-validation.log`:

- **32 valores** (8 entradas × 4) comparados Java 25 contra nativo, con el binario ejecutado sin Java en `PATH`.
  El fixture usa el constructor mixto `Node(int,Node)`, `step()` que devuelve `next`, `self()` que devuelve
  `this` y `pick(int,Node)` con dos `areturn`; la lectura encadenada `head.step().step()` llega al último nodo y
  el resultado combina los tres caminos con `int` del argumento.
- **Guarda sin opt-in:** sin `MC_AOT_RAYON_PROJECT_REFERENCES` no se traduce nada de esto y no se produce binario.
- **Guarda de firma:** con el opt-in puesto, una firma fuera del perfil (`(Ljava/lang/String;)I`) sigue dando
  `concurrent-int: firma no soportada` y no produce binario. El opt-in no es un «acepta todo».

## Q-AB-3: `completed-only` honra su nombre

Cambio de perfil que entra en el mismo commit porque es la mitad de B del acuerdo pendiente:

- `MC_AOT_FUTURES=restricted` sigue siendo el canónico y enciende futuros completados **y** pendientes.
- `MC_AOT_FUTURES=completed-only` —el valor que A ya aceptaba— enciende los futuros completados y **rechaza
  crear un futuro pendiente** con `futuro pendiente: MC_AOT_FUTURES=completed-only no lo admite (usa restricted)`.
  Se honra el nombre en vez de reinterpretarlo: si aquí significara «lo mismo que restricted», un operador que
  pidió solo completados recibiría en silencio semántica que no pidió.
- Cualquier otro valor sigue rechazándose (`valor de MC_AOT_FUTURES no soportado`), para que una errata no
  encienda el perfil por accidente.

Evidencia: `check-rayon-completed-future.py` ejecuta el fixture completado con el alias histórico **y** con
`MC_AOT_FUTURES=completed-only` (90 resultados idénticos a Java); `check-rayon-pending-future.py` prueba que
`completed-only` rechaza el fixture de futuro pendiente. Del lado de A sigue pendiente aceptar `restricted` como
alias en `numeric.rs` para que el canónico funcione en su backend; la intersección ya es no vacía con este cambio
(`check-futures-optin-shared.py`: «los dos backends aceptan `completed-only`»).

## Límites que siguen en pie

- Sin despacho de subclases: el tipo declarado es la clase exacta, no una jerarquía.
- Sin `String` ni arrays como valor de retorno, sin genéricos ni puentes sintéticos.
- Sin excepciones Java: un retorno `null` se admite como valor, pero desreferenciarlo en el frame llamador
  falla con el diagnóstico del heap, no con `NullPointerException`.
- Sin GC, sin `volatile`, sin modelo de memoria: lo único declarado es el mutex del heap y los invariantes
  probados.
- El cableado de `Main` sigue detenido en `new ForkJoinPool`; esto es un subperfil del generador.

## Reproducir

```sh
export JAVA_HOME=/ruta/al/jdk25 TMPDIR=/var/tmp
python3 mc-aot/tests/check-rayon-project-ref-returns.py
python3 mc-aot/tests/check-rayon-completed-future.py
python3 mc-aot/tests/check-rayon-pending-future.py
python3 mc-aot/tests/check-futures-contract.py
```
