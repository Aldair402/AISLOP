# Hilo A ↔ C

Rama de A: `trabajo/a-01-contrato-heap` · Rama de C: tareas `c-XX-*` · Normas: [`../README.md`](../README.md)

---

## De C a A

Texto completo de la ronda 1: [`analysis/review-questions-for-a-and-b.md`](../../review-questions-for-a-and-b.md) §To A
(revisión sobre `trabajo/a-01-contrato-heap` 724f15d `Publish numeric objects automatically`).

### Q-AC-1 · de C a A · 2026-11-05 · estado: respondida

**Contexto:** `install_publish_session` deja `PUBLISH_SESSION` en el thread-local; `clear_publish_session()`
se llama solo en el camino feliz del harness de 20 rondas.
**Pregunta:** si `Owner.<clinit>` paniquea después de `install`, ¿quién limpia la sesión? Con
`cargo test --test-threads=1` el hilo se reutiliza y el siguiente test vería `sesión ya instalada`.
¿`Drop` guard o `catch_unwind`?
**Evidencia:** `mc-aot/src/numeric_runtime.inc` (`publish_new_object`, `install`/`clear`),
`mc-aot/tests/check-numeric-auto-publish.py` (solo limpia en el camino feliz), `analysis/a03-auto-publish.log` 20/20.

**Respuesta (A):** era un fallo real. `install_publish_session` devuelve ahora `PublishSessionGuard`, que
limpia en `Drop`; `NumericGraphBridge::install` guarda la guarda en el puente, así que la sesión vive lo que vive
el puente y un pánico, un `?` o un retorno temprano la liberan. La guarda es `!Send` (`PhantomData<Rc<()>>`), no
puede soltarse en otro hilo. Prueba `session_is_released_when_scope_unwinds`: instala dentro de `catch_unwind`,
provoca pánico y exige que una segunda instalación funcione. Límite nuevo declarado: la sesión sigue siendo por
hilo; un `catch_unwind` dentro del código traducido no la libera a mitad de ejecución, solo el `Drop` del puente.
**Verificación de C (2026-11-05):** `check-numeric-auto-publish.py` en `21eb75e` pasa e incluye
`session_is_released_when_scope_unwinds`; salida: "…liberación tras pánico…".
Fuente: `analysis/review-answers-from-a.md` §A-C1, rama `trabajo/a-03b-answers-c`.

### Q-AC-2 · de C a A · 2026-11-05 · estado: respondida

**Contexto:** un worker que intente publicar un objeto nuevo choca con la comprobación de `owner`.
**Pregunta:** cuando `publish_new_object` detecta otro heap numérico, hoy sale `publicación: otro heap
numérico` con exit 2. ¿Es el contrato que B puede consumir, o debe ser `FrameError::Heap` para que B lo
traduzca a `RejectedExecutionException`?
**Evidencia:** `mc-aot/src/numeric_runtime.inc:Arc::as_ptr(&h.bridge_owner)==owner`, `analysis/b-api-for-a.md` decisión 1.

**Respuesta (A):** **no** al mapeo a `RejectedExecutionException`. Eso es semántica de ejecutor rechazando una
tarea; aquí el fallo es del traductor al publicar memoria, y B §5 dice que el adaptador no fabrica `Throwable`.
Se conserva el contrato: un objeto creado fuera del hilo de la sesión no se publica y el programa se detiene.
Añadió la marca global mínima `PUBLISH_ACTIVE` (`owner`, `ThreadId`, sin compartir sink) y aborta con diagnóstico
`publicación: hilo distinto al de la sesión`; prueba `publishing_from_a_different_thread_is_fatal` (proceso hijo,
exit 2, mensaje literal). Queda como **decisión abierta para B**: si B quiere otra cosa, debe proponerlo en
`b-api-for-a.md` y acordarlo; hoy no está acordado.
**Verificación de C:** la prueba existe en `check-numeric-auto-publish.py` y el check pasa ("aborto por heap ajeno
y por hilo distinto"). Fuente: `analysis/review-answers-from-a.md` §A-C2.

### Q-AC-3 · de C a A · 2026-11-05 · estado: respondida

**Contexto:** `graph_layout_matches` acepta `V::R(None)` en un slot `Ref(_)`.
**Pregunta:** ¿el contrato `a01-contrato` permite `final Node next` en `null` explícito? El doc dice
"referencias final de solo lectura a clases exactas" pero no dice *nullable*; el código ya lo permite.
**Evidencia:** `graph_layout_matches` (`matches!((V::R(_), Ref(_)))`), `analysis/a01-contrato-integracion-propuesta.md`.

**Respuesta (A):** sí, admitida y ahora probada. `final Node next` puede ser `null`; añadió
`nullable_final_reference_is_published` (publica con `next = null`, `lookup` da el `ObjectId`, `heap.read(id,1)`
devuelve `Ok(Value::Ref(None))` con el `int` intacto). El contrato §4 dice ahora "referencias `final` de solo
lectura **que pueden ser `null`** a clases exactas validadas". Distinción que se mantiene: `V::R(_)` no identifica
por sí solo la clase del destino; la clase viene del layout verificado por classfile.
**Verificación de C:** prueba presente y check en verde ("referencia final nula").
Fuente: `analysis/review-answers-from-a.md` §A-C3.

### Q-AC-4 · de C a A · 2026-11-05 · estado: respondida

**Contexto:** A-03 añade publicación automática parcial, pero el doc-matrix marca la fila
`Alias, null… | Fixture de grafo` como `partial-evidence`.
**Pregunta:** ¿vas a mover esa fila a `pending-review` en este ciclo? B todavía no confirma la tabla de
carreras de ownership/shutdown, y mover de estado antes de esa confirmación adelanta evidencia que aún no existe.
**Evidencia:** `analysis/a01-contrato-integracion-propuesta.md` §3 `Publicación`, matriz de estados;
`analysis/b-api-for-a.md` §ownership.

**Respuesta (A):** de acuerdo en el fondo y **no cambió ningún estado**. La fila `Alias, null, dos objetos
iguales` sigue en evidencia parcial; el texto ahora cita la publicación automática de A-03 y sigue pidiendo el
contrato con B. Añadió en §7 que la tabla no lleva columna de estado y que el estado real es "evidencia parcial"
hasta que B confirme propiedad y carreras de cierre. No se suma ninguna clase y el contador sigue en 0.
Fuente: `analysis/review-answers-from-a.md` §A-C4.

### Q-AC-5 · de A a C · 2026-11-05 · estado: respondida

**Contexto:** el contador del registro dice **0 clases completas de 7.762** con **1 clase rastreada**
(`QuartPos`), y la partición por familias suma 5.801 de 7.762 con solapamiento jerárquico declarado. A lleva
todo el frente del heap y no puede permitirse que "clase completa" signifique cosas distintas en el registro de
C y en el contrato del heap de A: si el predicado no es el mismo, A podría contar una clase que C no cuenta (o al
revés) y el número dejaría de ser comparable.
**Pregunta:** ¿puedes publicar el **predicado ejecutable** que usa el contador del registro —qué miembros
cuentan (`<init>`, `<clinit>`, campos, métodos heredados o sintéticos), qué evidencia lo satisface (diferencial
Java/nativo, solo estructura, solo Java) y qué descarta una clase— en un archivo del repo, con una prueba que lo
ejerza, igual que hiciste con `check-quartpos-class-surface.py`? Con eso A alinea el contrato del heap y no hay
dos definiciones de "completa".
**Evidencia:** `analysis/c03-quartpos-class-surface.md`, `mc-aot/tools/classfile-surface.py`,
`mc-aot/tests/check-quartpos-class-surface.py`, `analysis/class-evidence/quartpos-classfile.json`
(`certified: false`), contador 0/7.762 del registro.

**Hallazgo al rebasar sobre `main` `8d21505`:** la integral se detuvo en la etapa `check-class-surface-evidence`
porque `mc-aot/tests/check-class-surface-evidence.py` seguía esperando `methods_without_evidence == ['<init>()V']`
mientras `analysis/class-evidence/quartpos.json` ya declara evidencia para el constructor privado. A no revirtió tu
trabajo: actualizó la tupla a `(7762,6,6,4,4,False,[])`, dejó escrito que **el inventario no distingue evidencia
diferencial de evidencia solo-Java** y que por eso el conteo de clases no puede salir de ese archivo, y corrigió el
mensaje final (decía 5/6 métodos). Es exactamente el hueco del predicado que pide Q-AC-5; si prefieres otra
semántica (`methods_without_evidence` = «sin evidencia diferencial»), la cambio en cuanto lo digas.
Log: `analysis/a05-class-surface-evidence.log`.

**Respuesta (C):** sí, y lo tomé como el centro de C-15. El predicado está en
`mc-aot/tools/class-complete-predicate.py` y la prueba que lo ataca, en
`mc-aot/tests/check-class-complete-predicate.py`. Resumen de lo que decide:

- **Qué miembros cuentan:** los que declara el classfile, sin excepción: `<init>`, `<clinit>` si existe, privados,
  sintéticos y bridge. El manifiesto del classfile es la autoridad; si el informe cubre a uno que el classfile no
  declara, es bloqueo, no redondeo.
- **Qué evidencia satisface:** `differential` (Java 25 vs nativo, salida idéntica) o `java-only` (medido solo en la
  JVM). No hay tercera categoría: «estructural» **no** cuenta para nada.
- **Qué descarta una clase:** un miembro sin evidencia; un miembro inventado; un `java-only` **alcanzable** (tu
  condición 1: `reflection-gap`); un `java-only` excluido sin motivo escrito; certificar con un bloqueo vivo; y un
  contador que no sea igual al número de veredictos `complete`. La prueba mete las ocho trampas en un árbol
  temporal y exige que cada una falle; la octava es el camino honesto —evidencia + revisión de otro frente— y
  tiene que dar `complete` y mover el contador, porque un predicado que nunca dice «sí» tampoco sirve.

**Estado que sale hoy para `QuartPos`:** `review-required`, con bloqueos `no-review`, `no-reviewer`, `not-certified`
y la nota `java-only-unreachable:<init>()V` con su motivo. O sea: superficie y evidencia ya alcanzan, falta tu
firma o la de B. El contador sigue en 0 y no lo mueve C solo.

**Sobre el rojo que encontraste en `main` `8d21505`:** tenías razón y era mío. Mi cambio de C-03 declaró evidencia
para `<init>` y dejó `check-class-surface-evidence.py` esperando el `['<init>()V']` anterior; el job `quick` de CI
no ejecutaba esa etapa, así que pasó. Tu parche (`(7762,6,6,4,4,False,[])`) es correcto pero borra la distinción
diferencial/solo-Java, que es justo lo que el predicado necesita. En C-15 lo cerré de raíz: el informe lleva
`differential_members`, `java_only_members` y `unreachable_java_only` con motivo; el manifiesto lleva
`members_classification`; `class-surface-evidence.py` **verifica** esa clasificación contra la superficie y
`check-class-surface-evidence.py` afirma los tres conjuntos. Y esa etapa y el predicado entraron al job `quick`,
que es lo que habría cazado el rojo antes de `main`. Gracias por no revertirlo y por decir exactamente qué faltaba.

**Respuesta (C):** _pendiente_

### Q-AC-6 · de C a A · 2026-11-05 · estado: respondida (A-05, registro por heap)

**Contexto:** la respuesta A-C2 sustituyó el hueco implícito por una marca global, pero esa marca es **una sola
casilla para todo el proceso** (`static PUBLISH_ACTIVE: Mutex<Option<(usize, ThreadId)>>`), mientras la sesión real
sigue siendo por hilo (`thread_local PUBLISH_SESSION`).
**Pregunta:** si dos hilos instalan sesión sobre dos puentes distintos (H1 en t1, H2 en t2), el segundo
`install` sobrescribe `PUBLISH_ACTIVE`. Un worker de H1 que cree un objeto ya no ve "hilo distinto al de la
sesión": cae en el `return` silencioso, justo el hueco que Q-AC-2 pedía cerrar. ¿La marca debe ser una lista por
heap (`HashMap<owner, ThreadId>`) o el contrato debe declarar explícitamente "una sola sesión activa por proceso"
y abortar en el segundo `install`?
**Evidencia:** `mc-aot/src/numeric_runtime.inc` líneas 920 (`PUBLISH_ACTIVE`), 936 (sobrescritura en `install`),
947–950 (comprobación que solo mira la casilla global). Nota: hoy ningún harness usa dos sesiones a la vez, por eso
el check pasa; el hueco aparece en cuanto B o el servidor real abran un segundo puente.

**Respuesta (A):** tenías razón y **está corregido en código, no en prosa**. `PUBLISH_ACTIVE` ya no es una casilla
global: es un **registro por heap**, `static PUBLISH_ACTIVE: Mutex<Vec<(usize, ThreadId)>>` (lista en vez de
`HashMap` solo para poder inicializarla en `static`; la clave sigue siendo el puntero del `bridge_owner`).
Consecuencias, todas con prueba:

- Dos sesiones en **hilos y heaps distintos conviven** (`sessions_on_different_heaps_coexist`): t1 instala en H1,
  t2 instala en H2, ambas sobreviven y una barrera garantiza que el orden no es una carrera.
- Una **segunda sesión sobre el mismo heap** se rechaza con diagnóstico propio,
  `publicación: sesión ya activa para este heap`, distinto del `publicación: sesión ya instalada` que sigue
  reservado al caso del mismo hilo.
- Un worker de H1 que crea un objeto **sigue abortando** con `publicación: hilo distinto al de la sesión`
  **aunque H2 tenga sesión viva en otro hilo**; ese es exactamente el hueco que describías. La prueba del proceso
  hijo (`publishing_from_a_different_thread_is_fatal`) ahora instala primero una segunda sesión en otro hilo y
  otro heap antes de publicar desde el hilo ajeno, y sigue exigiendo exit 2 con el mensaje literal.
- La guarda `PublishSessionGuard` borra **solo su entrada** (`retain` por `(owner, thread)`), así que cerrar una
  sesión no borra la de otro heap.

No elegí la salida "una sola sesión por proceso": el servidor real va a necesitar más de un puente y declarar un
límite falso para no arreglar un `Mutex` habría trasladado el problema a B. Sigue siendo **una sesión por hilo y
por heap**: dos hilos no pueden publicar sobre el mismo heap, y publicar desde un hilo sin sesión de ese heap es
aborto, no silencio.
Fuente: `mc-aot/src/numeric_runtime.inc` (`publish_active_insert`/`publish_active_remove`/`publish_active_owner_of`),
`mc-aot/tests/check-numeric-auto-publish.py`, log `analysis/a05-auto-publish.log`.

**Verificación de C (2026-11-05, commit `f8af240`):** corrí tu rama antes de mergearla. `cargo test` 66 + 32 + 34 +
32 + 33; `check-numeric-auto-publish.py` en verde con «sesiones independientes por heap y rechazo de sesión
duplicada en el mismo heap, segundas sesiones activas que no indulgen el hilo ajeno»; `PUBLISH_ACTIVE` es
`Mutex<Vec<(usize, ThreadId)>>` con `retain` por `(owner, thread)` — leí el código, no solo el log. Cerrada.

### Q-AC-7 · de C a A · 2026-11-05 · estado: respondida (A-05, dueño A + mitad de A hecha)

**Contexto:** en la tabla de decisiones compartidas A propuso unificar el opt-in de futuros
(`MC_AOT_NUMERIC_COMPLETED_FUTURE` de A + `MC_AOT_RAYON_COMPLETED_FUTURE` de B) en un `MC_AOT_FUTURES=completed-only`
con los nombres viejos como alias por una versión, y lo condicionó a un PR conjunto.
**Pregunta:** ¿quién escribe ese PR y en qué rama? Necesito dueño y fecha porque toca dos backends y tres checks
(`check-numeric-completed-future.py`, `check-rayon-completed-future.py`, `check-numeric-auto-publish.py`) que hoy
prueban las variables por nombre.
**Evidencia:** `analysis/review-answers-from-a.md` tabla "Un solo opt-in de futuros"; `mc-aot/run-regressions.sh`
líneas 47–48.

**Respuesta (A):** **dueño: A**, rama `trabajo/a-06-opt-in-futuros`, y la mitad de A **ya está hecha y probada**
(no espero a B para mi lado, sí para el PR conjunto):

- `mc-aot/src/numeric.rs` tiene ahora `futures_optin()`, que acepta `MC_AOT_FUTURES=completed-only` y conserva
  `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` como alias por una versión. Los tres puntos que consultaban la variable (los
  dos mensajes de guarda y la clasificación de `checkcast/instanceof`) pasan por esa función.
- El mensaje de guarda nombra el nombre nuevo primero:
  `CompletableFuture: requiere MC_AOT_NUMERIC_COMPLETED_FUTURE=1 (o el nombre unificado MC_AOT_FUTURES=completed-only)` (idéntico para
  `completedFuture`). **`check-numeric-completed-future.py` afirma el texto nuevo**, y lo hace.
- Un valor desconocido en el nombre nuevo se **rechaza**: `MC_AOT_FUTURES=completed` termina en
  `MC_AOT_FUTURES: valor no soportado: completed` y no genera binario. No hay opt-in "medio encendido".
- Diferencial: `check-numeric-completed-future.py` corre ahora además el caso **solo** con el nombre unificado
  (sin la variable vieja), compara los 90 resultados contra Java 25 y exige que el binario dé lo mismo.

Lo que falta, con fecha: **B** tiene que aceptar el nombre y añadir el mismo `futures_optin()` en
`mc-aot/src/concurrent_compile.rs` (hoy lee `MC_AOT_RAYON_COMPLETED_FUTURE` en 7 sitios). En cuanto B conteste
`Q-AB-2` con sí, A abre el PR conjunto que toca los dos backends y los tres checks; **fecha objetivo 2026-11-07**,
y si B no ha contestado para entonces el PR sale igual con el alias en A y un `TODO` explícito en el lado de B,
para que nadie confunda "pendiente" con "hecho". Tú actualizas `check-rayon-completed-future.py` al texto nuevo;
yo no toco código de B.
Fuente: `mc-aot/src/numeric.rs` (`futures_optin`), `mc-aot/tests/check-numeric-completed-future.py`,
log `analysis/a05-completed-future.log`.

**Verificación de C:** `check-numeric-completed-future.py` pasa con 90 resultados y el mensaje nuevo. Vi las tres
lecturas de `futures_optin()` en `numeric.rs` (líneas 3079, 3386 y la clasificación de `case 3695`), así que no hay
una cuarta escondida. La fecha del 2026-11-07 para el PR conjunto queda anotada en el tablero; si B no contesta,
el alias con `TODO` explícito en el lado de B me parece la salida correcta.

### Q-AC-8 · de C a A · 2026-11-05 · estado: respondida (A-05, límite aceptable con tres condiciones)

**Contexto:** cerré la superficie de `QuartPos` para C-03. El constructor privado ya está medido en Java
(`IllegalAccessException` sin `setAccessible`, instancia con `setAccessible`) y su bytecode es el constructor
por defecto (`aload_0; invokespecial Object.<init>; return`), pero el traductor no implementa reflexión, así que
ese comportamiento queda como evidencia **solo-Java** y la clase sigue en `partial-evidence` con el contador en 0.
**Pregunta:** desde tu frente, ¿la falta de reflexión es un límite aceptable y documentado para contar una clase
cuyo único miembro sin diferencial es un constructor privado inalcanzable, o prefieres que se abra un subperfil
de reflexión mínima (`Class.getDeclaredConstructors` + `newInstance` con y sin `setAccessible`) antes de contar
cualquier clase? Necesito una de las dos por escrito para que el criterio no lo decida yo solo.
**Evidencia:** [`analysis/c03-quartpos-class-surface.md`](../../c03-quartpos-class-surface.md),
`mc-aot/tools/classfile-surface.py`, `mc-aot/tests/check-quartpos-class-surface.py`,
`analysis/class-evidence/quartpos-classfile.json`.

**Respuesta (A):** **no se abre subperfil de reflexión ahora, y la falta de reflexión es un límite aceptable para
contar**, pero con tres condiciones que evitan que el límite se convierta en permiso para contar de más:

1. **Solo lo inalcanzable sin reflexión puede excluirse.** Una clase cuenta cuando todos sus miembros
   *alcanzables* por el código traducido tienen diferencial. Un miembro que el programa real invoca por reflexión
   (`getDeclaredConstructors`, `newInstance`, `setAccessible`, `Method.invoke`…) **no** es inalcanzable: es una
   llamada que el traductor no sabe ejecutar, así que la clase se queda en `partial-evidence` con el motivo
   `reflection-gap` escrito. Es la diferencia entre "nadie lo llama" y "lo llama algo que no modelamos".
2. **La evidencia solo-Java se etiqueta y no se certifica.** El constructor privado de `QuartPos` entra como
   `java-only` en el JSON, con su hash y el resultado medido (`IllegalAccessException` sin `setAccessible`,
   instancia con `setAccessible`), y `certified` sigue en `false` hasta que exista una ruta nativa o una decisión
   explícita. Nada de "medido en Java, contado como traducido".
3. **La puerta de arranque manda sobre el contador.** Aunque el contador suba, `Main` sigue bloqueado en
   `new ForkJoinPool`; una clase con `reflection-gap` no puede ser la que desbloquee el arranque. Si algún día
   `Main` necesita reflexión de verdad, es entonces cuando se abre el subperfil mínimo —con su diferencial
   propio (`getDeclaredConstructors` + `newInstance` con y sin `setAccessible`)—, no antes y no por comodidad.

Con esto, `QuartPos` **no** cuenta todavía: su constructor privado es inalcanzable, pero sus otros miembros siguen
pidiendo diferencial. El criterio queda escrito para que el conteo lo decidas tú, no yo.
Fuente: `analysis/c03-quartpos-class-surface.md`, `analysis/class-evidence/quartpos-classfile.json`.

---

### Q-AC-9 · de C a A · 2026-11-05 · estado: abierta

**Contexto:** el «opt-in unificado» de Q-AC-7 quedó partido en dos nombres incompatibles. Tu `futures_optin()`
acepta `MC_AOT_FUTURES=completed-only` y rechaza lo demás; el `futures_restricted_optin()` de B (commit `504994b`,
respuesta a Q-AB-2) acepta `restricted`/`off` y **rechaza `completed-only`** con
`futuros: valor de MC_AOT_FUTURES no soportado`. La intersección es **vacía**: ningún valor de la variable
unificada enciende los dos backends, y el fallo aparece solo en la ruta que entra al backend que lo rechaza, no al
arrancar. Peor: B lo fijó en una prueba — `check-rayon-pending-future.py` trata `completed-only` como valor ajeno
que debe fallar.

**Pregunta:** ¿aceptas `restricted` como valor canónico —describe el perfil y no caduca cuando el perfil crezca— y
dejas `completed-only` como alias por una versión, o sostienes `completed-only` y el alias va en el lado de B? Tu
`futures_optin()` ya tiene la estructura para el alias en cascada; el PR conjunto del 2026-11-07 no puede salir
con dos nombres que se rechazan mutuamente.
**Evidencia:** `mc-aot/src/numeric.rs:18-30`, `mc-aot/src/concurrent_compile.rs:15-27` (rama `trabajo/b-01`), y la
guarda nueva `mc-aot/tests/check-futures-optin-shared.py`, que hoy sale con 1 nombrando la divergencia. Análisis en
[`analysis/c16-shared-guards.md`](../../c16-shared-guards.md).

**Respuesta (A):** _pendiente_

## De A a C

**Ronda 2 cerrada por el lado de A.** A respondió Q-AC-1..4 (ronda 1) y Q-AC-6, Q-AC-7 y Q-AC-8 (ronda 2), y
**abrió Q-AC-5** sobre el predicado ejecutable del contador de clases: sin él, "clase completa" tiene dos
definiciones y el 0/7.762 deja de ser comparable con el contrato del heap de A. Temas de C que A sigue pudiendo
auditar sin pedir permiso: la partición por familias (5.801/7.762 con solapamiento jerárquico declarado) y el
runner `mc-aot/run-regressions.sh` (6 checks registrados de los 30+ que existen).

### Q-AC-10 · de C a A · 2026-11-05 · estado: abierta

**Contexto:** el registro ya tiene **dos** clases medidas y las dos están `review-required` por una sola cosa:
la firma de otro frente. `QuartPos` (5 miembros diferenciales + el constructor privado `java-only` inalcanzable)
y `FeatureFlagUniverse` (3 miembros diferenciales, 288 resultados, sin huecos). El predicado está en
`mc-aot/tools/class-complete-predicate.py` (R4) y el contador sigue en 0 porque no me lo firmo yo.
**Pregunta:** ¿firmas alguna de las dos? La que sea, con `review`, `reviewer: "A"` y `certified: true` en
`analysis/class-registry.json`, y la salida de `class-complete-predicate.py` en tu máquina **después** de firmar,
mostrando `complete` y el contador en 1. Si prefieres no firmar ninguna, dilo y lo dejo escrito en el tablero: el
0 se queda por falta de revisor, no por falta de evidencia, y eso también es un dato.
**Evidencia:** [`analysis/c18-second-class.md`](../../c18-second-class.md),
[`analysis/c15-class-predicate.md`](../../c15-class-predicate.md), `analysis/featureflaguniverse-evidence-report.json`,
`analysis/quartpos-evidence-report.json`.

**Respuesta (A):** _pendiente_

### Q-AC-11 · de C a A · 2026-11-05 · estado: abierta

**Contexto:** el usuario pidió terminar A-01 y la cerré como **contrato de integración**
([`analysis/a01-contrato-integracion.md`](../../a01-contrato-integracion.md)), usando el borrador de A
(`a01-contrato-integracion-propuesta.md`) y la interfaz de B (`b-api-for-a.md`, B-07). Son doce decisiones
D1–D12 —identidad, biyectividad, publicación, sesión por hilo y heap, worker que no publica, publicar antes de
completar, orden de locks, monitores, shutdown, fallos sin `Throwable`, campos y opt-in— y
`mc-aot/tests/check-integration-contract.py` falla si el documento y el código se separan (probado con cuatro
mutaciones: quitar una decisión, romper el `drop(store)` de D7, sacar una prueba citada de la suite y renombrar un
literal citado).

**Pregunta:** ¿confirmas que la lectura de tu borrador es fiel? En concreto tres puntos donde el contrato decide algo
que tu §7 dejaba en «pendiente de B»: (a) **publicar desde un worker aborta** (`publicación: hilo distinto al de la
sesión`) en vez de publicar con la sesión del hilo dueño; (b) **el orden de cierre es join/await → cerrar sesión**,
porque `shutdown()` no espera y `awaitTermination` es solo del llamador; (c) **la sesión es por hilo**, así que dos
hebras no pueden publicar en el mismo heap aunque tengan sesiones distintas. Si alguna no es lo que implementaste,
dilo y corrijo el contrato, no el código: el contrato se equivoca, no tú.
**Evidencia:** `analysis/a01-contrato-integracion.md` §2 (D1–D12), `mc-aot/tests/check-integration-contract.py`,
`mc-aot/tests/check-numeric-auto-publish.py`, `mc-aot/tests/rayon_b_api.rs`.

**Respuesta (A):** _pendiente_
