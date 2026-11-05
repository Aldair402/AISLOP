# A-01: propuesta de contrato entre backend numérico y concurrente

**Estado: borrador del frente A; pendiente de revisión del frente B.** No cambia la API ni declara A-01 terminada. Referencias de implementación y pruebas: `mc-aot/src/numeric_runtime.inc`, `numeric_concurrent_graph_bridge.inc`, `concurrent_heap.rs`, `tests/check-numeric-concurrent-graph.py` y `analysis/heap-bridge-design.md`.

## 1. Alcance de la primera puerta

La meta es que bytecode Java traducido por el backend principal pueda publicar un objeto y ejecutar trabajo con el mismo estado y monitor desde el backend concurrente, sin ensamblado ni scheduling manual del harness. El perfil inicial no promete compatibilidad Java general, ni tipos ajenos a lo validado, ni arranque de `Main`.

**Implementado hoy, solo en harness:** objetos ordinarios numéricos compartidos por handles; `int` y lectura de referencias finales de clase exacta, si cada destino ya se registró; un monitor reentrante común; mapa de identidad por sesión. `NumericGraphBridge` aún recibe layouts manuales y no une estáticos, clases ni la llamada Java entre backends. Ver límites del roadmap; nada de este documento hace que esos faltantes funcionen.

## 2. Identidad y pertenencia

- El `Heap` numérico es propietario del índice `usize`; nunca se interpreta como `ObjectId` del otro heap. `Heap.bridge_owner` identifica el dueño de la sesión. Un índice sin su propietario **no es** una identidad global ni un argumento válido de la API.
- En una sesión, el mapa debe ser biyectivo para objetos registrados: `(dueño, índice numérico)` ↔ `(SharedHeap, ObjectId)`. Dos referencias al mismo objeto deben resolver al mismo ID del destino; dos objetos distintos no pueden confundirse, incluso si tienen campos iguales. La publicación de un alias, no solo su contenido, se comprueba.
- `null` se representa como `None` en ambos lados y no se registra. Una referencia de heap ajeno, índice inexistente, sesión equivocada, clase incompatible o destino todavía no registrado se rechaza; no se inventa un objeto nuevo ni se convierte a null.
- La identidad interna actual usa `Arc` del almacenamiento como clave confiable y un dominio de sesión. Es un detalle privado, no una interfaz para adaptadores no confiables ni una promesa de identidad persistente entre ejecuciones. El mapa/heap mantienen vivas las estructuras mientras corresponda.

## 3. Ciclo de vida y publicación propuestos

1. **Preparación exclusiva:** el llamador posee `&mut Heap`, verifica el classfile y configura la sesión. La conversión de `Array::Obj` a `SharedObj` conserva la instancia, campos y un único monitor; se rechaza convertir un objeto con monitor monohilo adquirido o `LocalObj`.
2. **Registro:** asociar al dominio y heap correctos cada objeto alcanzable que el perfil admita. La lectura de una referencia cuyo destino aún no esté registrado debe fallar. Para ciclos/autoalias, registrar todos los nodos antes de publicar el grafo; no depender de un recorrido recursivo que se bloquee.
3. **Publicación:** solo después de verificar y registrar el conjunto necesario, entregar IDs a workers bajo un mecanismo de publicación sincronizado. Existe un opt-in parcial (A-03, `analysis/a03-auto-publish.md`): `object_new` publica los objetos admitidos al construirlos a través de `PublishSink` y el harness deja de enumerar instancias; la sesión es por hilo y no publica lo que crean los workers. Sigue prohibido compartir `&mut Heap` con varios hilos y suponer que estáticos/clases ya están unidos; estáticos, unión de programas y `SharedHeap` siguen siendo manuales.
4. **Ejecución:** cada worker usa `SharedHeap`/frames y acceso delegado a los campos/monitor admitidos; el llamador puede usar la ruta numérica con el mismo handle. Si se invoca código o se espera una tarea, no se retiene ningún lock global ni préstamo exclusivo del heap que el worker necesite.
5. **Cierre:** esperar que las tareas del perfil hayan terminado antes de retirar la sesión. La sesión de publicación es por hilo y su guarda la libera en `Drop` (pánico o retorno incluidos); publicar desde otro hilo aborta con diagnóstico y **no** se convierte en excepción Java. Ver `review-answers-from-a.md`. Actualmente el adaptador usa `Weak`: después de cerrar, acceso/entrada fallan; un objeto ya asociado a otro dominio en el mismo `SharedHeap` no se readjunta silenciosamente. GC, reutilización de índices y reapertura segura no están diseñados. No se permite cerrar mientras haya operaciones concurrentes sin definir y probar ese protocolo.

**Pendiente de B:** mecanismo concreto de publicación, propiedad de la sesión durante tareas, orden de shutdown y forma de indicar cancelación o fallos. A-01 no se cierra hasta acordarlo y revisar casos de carrera.

## 4. Campos y layouts

- El layout se obtiene del classfile, no de `V::I`: esa etiqueta también representa boolean/byte/short/char. La clase y la versión del JAR se identifican por hash; flags, orden y descriptores de instancia se verifican antes de generar o conectar el adaptador.
- Propuesta conservadora inicial para A-02: clase `final` directa de `java/lang/Object`, sin interfaces ni `<clinit>`; campos de instancia `int` no `final`/no `volatile`, y referencias `final` de solo lectura **que pueden ser `null`** a clases exactas validadas por la misma política. Campos estáticos no se comparten y deben rechazarse en este primer generador. Arrays, cadenas, subtipos, tipos numéricos adicionales y mutación de referencias se rechazan.
- El caso `int final` no debe mapearse a un slot escribible: el puente actual no distingue final por slot. Se rechaza hasta que se demuestre una API de lectura/escritura que preserve esa diferencia. Tampoco se infiere semántica `volatile` a partir del mutex interno.
- `read`/`write` de cada objeto compartido son protegidos por su mutex de campos. Una operación RMW interna como `add_int` **no es** el bytecode `i++` ni prueba comportamiento de data races Java. La prueba con incremento debe usar el monitor Java traducido.

## 5. Locks y progreso

Reglas propuestas para el primer perfil, sujetas a pruebas y revisión B:

- `SharedHeap` puede tomar el mutex de su tabla solo para verificar ID/clase y clonar un handle; debe soltarlo **antes** de entrar al adaptador, esperar un monitor o ejecutar código/una tarea. Para referencias devueltas se vuelve a validar pertenencia después de la llamada.
- Al leer un campo que es referencia, copiar el valor bajo el lock de campos y liberarlo **antes** de tomar el lock del mapa de identidad. Nunca mantener campos y mapa a la vez durante esta resolución. No adquirir el lock de un objeto destino mientras se conserva el lock de campos de origen.
- El monitor Java es reentrante por hilo; se adquiere y libera por el mismo hilo. Mientras una sección Java lo posea puede haber accesos breves al lock de campos, pero ningún camino debe adquirir después ese monitor mientras conserve el lock de campos. Desenrollado/error debe liberar la guarda. No asumir orden global de adquisición entre distintos monitores Java.
- No esperar `join`, shutdown, inicialización de clases, condvar ni callbacks con el mutex de tabla/mapa/campos retenido. Los locks de implementación no deben escapar al código generado. Un interbloqueo entre monitores Java legítimo no se confunde con un deadlock añadido por el runtime.
- El prototipo ya suelta el lock global antes de delegar y separa lectura de campos/mapa; estas reglas no certifican los demás caminos ni el modelo de memoria JVM. Las pruebas deben usar timeout y detectar inversiones de locks.

## 6. Errores y fronteras

Distinguir: (1) excepción Java realmente modelada; (2) error explícito por operación no soportada; (3) fallo interno/invariante/poison/límite. Un panic Rust o `FrameError` no se presenta como excepción Java equivalente. El backend concurrente aún no traduce excepciones Java generales. No cubrir silenciosamente `wait`/`notify`, interrupción, CAS externo, inicialización de clase, Tracy activo ni logger ausente.

No se unen actualmente estaticos, class objects, arrays, String, colecciones, `CompletableFuture`, clases con inicializadores ni GC entre heaps. No afirmar que la factory real de Minecraft o `Main` usan el puente hasta ejecutar esa ruta.

## 7. Matriz mínima para acordar con B

| Caso | Exigencia del perfil | Evidencia previa / trabajo |
|---|---|---|
| Alias, null, dos objetos iguales | Misma identidad solo para el mismo objeto; null estable | Evidencia parcial: fixture de grafo y publicación automática (A-03, incluida referencia `final` nula); **falta** confirmación de propiedad y cierre por B. Esta tabla no tiene columna de estado |
| Heap ajeno, doble sesión y cierre | Rechazo explícito, sin leer o cambiar el objeto | Fixture de grafo; falta protocolo de cierre concurrente |
| Autoalias y ciclo de referencias | Identidad estable, sin retener locks anidados | Falta demostrar automáticamente todo el grafo |
| Tipo/final/volatile o hash alterado | Rechazar antes de publicar/generar | A-02; verificar classfile, no solo `V::I` |
| Monitor reentrante, contención y unwind | Un único monitor para ambos backends; progreso sin locks internos retenidos | Fixture actual; ampliar bajo publicación automática |
| Tarea falla o `join` espera | No inventar excepción Java; terminar/rechazar según perfil | B define executor/futuros y A integra |
| Estáticos y `<clinit>` | Inicialización/publicación/fallos coherentes o rechazo | A-05 y contrato común; no implementado |
| Main/`Util.makeExecutor` | Factory, handler, logging y cierre reales o guardas explícitas | A-07/B-06; todavía bloqueado |

**Revisión solicitada a B:** identidad y vida útil; posibilidad de callbacks/reentrada durante registro/espera; shutdown con tareas activas; diferencias entre errores Rust y excepciones Java; cómo versionar/verificar los layouts sin duplicar el parser. Registrar decisiones en issue/PR antes de implementar una interfaz compartida.
