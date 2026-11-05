# A-06 · Arrays de referencias de proyecto compartidos con el puente

**Rama:** `trabajo/a-06-shared-arrays` · **Base:** `main` `8d21505` · **Fecha:** 2026-11-05
**Autor:** MIlaSoraki &lt;mila.gastelum@autistici.org&gt;

Subperfil siguiente a A-04 (campos de referencia mutables). A-04 abrió la **escritura de un campo**; A-06 abre el
**contenedor**: un array de referencias de proyecto creado por el bytecode numérico se comparte con el heap
concurrente, cuyos elementos se leen y escriben con las mismas guardas que un campo `MutRef`.

## Qué se implementó

| Pieza | Dónde |
|---|---|
| `Array::SharedRefs(&'static str, NumericArrayHandle)` con `slots: Arc<Mutex<Vec<Option<usize>>>>` y monitor propio | `mc-aot/src/numeric_runtime.inc` |
| `share_project_array` (convierte `ProjectRefs` en `SharedRefs`, rechaza monitors monohilo y arrays no de referencias) | ídem |
| `publish_new_array` (mismo contrato de diagnóstico que `publish_new_object`) y ganchos `admits_array`/`publish_array` en `PublishSink` con implementación por defecto que **no** admite arrays | ídem |
| Carga y descarga de elementos (`0x32`/`0x53`), `arraylength`, `checkcast`/`instanceof` sobre arrays compartidos | ídem |
| `NumericGraphArrayLayout{array_class, element, length}` y `NumericGraphArray` como `ExternalObject` (los elementos son los slots) | `mc-aot/src/numeric_concurrent_graph_bridge.inc` |
| `NumericGraphBridge::attach_array` con validación de clase, longitud y forma; `lookup` también resuelve arrays | ídem |
| Arnés `check-numeric-shared-arrays.py` (diferencial Java 25 + cinco guardas) y registro en `run-regressions.sh` | `mc-aot/tests`, `mc-aot/run-regressions.sh` |

## Contrato de errores (todos medidos)

| Caso | Resultado |
|---|---|
| `attach_array` sobre un objeto en vez de un array | `grafo: solo arrays de referencias de proyecto` |
| clase de elemento distinta de la del array | `grafo: clase de array incompatible` |
| longitud del layout distinta de la del array | `grafo: longitud incompatible` |
| leer/escribir fuera de `0..length` | `grafo: índice fuera de rango` |
| escribir un `Value::Int` en un slot de referencia | `grafo: tipo de elemento incompatible` |
| escribir una referencia no publicada | `grafo: elemento no registrado o incompatible` |
| `lookup` antes de adjuntar | `grafo: objeto no publicado` |
| adjuntar dos veces el mismo array | idempotente, mismo `ObjectId` |

## Lo que este subperfil **no** hace

- **No publica arrays automáticamente.** El sink del puente no implementa `admits_array`; el array se adjunta con
  `attach_array` y su layout explícito, porque la clase del array (`[Lnet/minecraft/...;`) todavía no viene de un
  classfile verificado. `publish_new_array` ya existe y aborta con diagnóstico correcto si alguien activa el
  gancho, pero encenderlo es un paso aparte, no un efecto colateral de A-06.
- **No hay arrays de arrays, ni de primitivos compartidos, ni `clone`/`Arrays.copyOf` sobre un array compartido**
  (siguen rechazados por sus guardas actuales).
- **El bytecode concurrente no toca arrays**: el backend de Rayon no tiene `aastore`/`aaload` de proyecto. Es el
  mismo bloqueo de forma que en A-04 y se traslada a B (`Q-AB-3`).
- Sin GC, sin unión de los dos programas y sin `Main`: **0 clases completas**.

## Verificación

```
python3 mc-aot/tests/check-numeric-shared-arrays.py
  OK: array de proyecto compartido con el puente (4 elementos, null, sustituto publicado);
      Java 25 y nativo coinciden en sum=1043 y longitud 4; guardas de clase, longitud,
      índice, tipo y elemento no publicado; adjuntar es idempotente y el array no se
      publica solo; harness opt-in, no Main
```

El programa Java y el traducido ejecutan la misma secuencia (`bump` de los cuatro elementos, sustitución del
índice 2 por un `Node(1000)`, suma): Java 25 imprime `1043 4 1000` y el nativo devuelve `1043` con longitud `4`.

Logs: `analysis/a06-shared-arrays.log` y la integral `analysis/full-regressions-a06.log`.

```
analysis/full-regressions-a06.log: 319 etapas, EXIT_STATUS=0
  (318 en A-05; la etapa nueva es check-numeric-shared-arrays)
cargo test: 66 + 32 + 34 + 32 + 33
focalizadas: shared-arrays, mutable-refs, auto-publish, bridge-layout — todas en verde
```

Sigue igual lo de fondo: **0 de 7.762 clases completas**, `Main` detenido en `new ForkJoinPool`, sin servidor.
