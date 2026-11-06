# ¿Se pueden cerrar oficialmente los frentes A y B? Auditoría de cierre

**Fecha:** 2026-11-05 · **Autor:** MIlaSoraki &lt;mila.gastelum@autistici.org&gt;
**Base:** `main` `8d21505` + ramas `trabajo/a-04-mutable-refs`, `a-05-round2-publish-scope`, `a-06-shared-arrays`
**Pregunta que responde:** «¿podemos oficialmente terminar A y B totalmente?»

## 1. Respuesta corta

**No.** Ninguno de los dos frentes se puede cerrar «totalmente» hoy sin mentir en alguna de estas tres cosas:

1. **Que el heap esté modelado.** El puente comparte objetos, campos mutables, arrays de referencias y monitores,
   pero **solo en harness opt-in**: no hay unión de los dos programas, ni estáticos publicados, ni `<clinit>`
   compartido, ni GC, ni reflexión.
2. **Que los layouts salgan de clases reales de Minecraft.** El validador es estructural y el barrido vanilla da
   **0 de 687** candidatas: ningún layout del puente viene todavía de una clase del JAR oficial.
3. **Que eso acerque el servidor.** `Main` sigue detenido en `new no soportado: java/util/concurrent/ForkJoinPool`
   y el contador oficial sigue en **0 de 7.762 clases completas** (mitad: 3.881).

Lo que **sí** se puede hacer —y es lo que propongo abajo— es un **cierre de fase 1**: firmar las tareas cuyos
criterios de aceptación ya están cumplidos y reproducibles, y dejar por escrito, con nombre y dependencia, lo que
queda abierto. Cerrar por cansancio o por número de commits sería exactamente lo que el proyecto pidió no hacer.

## 2. Qué significaría «terminado» (criterio que propongo)

Una tarea se cierra cuando:

- **C1 · criterio de aceptación cumplido**, no «hay código»: el enunciado de la tarea dice qué debe observarse.
- **C2 · evidencia reproducible en la integral**: un `check-*.py` registrado en `run-regressions.sh` que falla si
  el comportamiento desaparece. Logs por etapa en `analysis/*-latest.log` y la integral con `EXIT_STATUS=0`.
- **C3 · límites declarados por escrito** en el mismo PR: qué NO cubre y qué haría falta para cubrirlo.

Un frente entero se cierra cuando todas sus tareas cumplen C1–C3 **y** la puerta de arranque de `ROADMAP.md` se
cumple (mundo, cliente autorizado, guardado y reinicio). Esa puerta no la decide A ni B: depende de C y del estado
real del traductor.

## 3. Frente A — Backend principal y unión de heaps

| Tarea | ¿Qué hay de verdad? | ¿Cerrable hoy? | Qué falta exactamente |
|---|---|---|---|
| **A-01** Contrato de integración | `analysis/a01-contrato-integracion-propuesta.md` con identidad, propiedad, publicación y límites; §4 admite `final` nullable; §7 dice que la matriz no lleva estado | **Sí, como contrato v1** | Falta la firma de B sobre ownership/cierre (B-07). El contrato **no** puede llamarse «unión de heaps»: describe dos heaps enlazados por el puente, no uno |
| **A-02** Generación/verificación de layouts | `numeric_bridge_layout.py` + `check-numeric-bridge-layout.py` (25 rechazos) + opt-in de mutable refs | **Parcial: no** | El validador es estructural; **0/687** clases vanilla pasan. Sin parseo de classfile real, ningún layout es de Minecraft |
| **A-03** Identidad y publicación automática | `object_new` publica al construir con `PublishSink`, guarda en `Drop`, aborto en otro hilo/heap, sesiones por heap | **Sí, como subperfil** | Solo objetos **creados después** de instalar la sesión, solo clases con layout del harness; sin estáticos, `<clinit>` compartido, arrays automáticos ni unión de programas |
| **A-04** Referencias y mutación | `MutRef` opt-in (`check-numeric-mutable-refs.py`, 20 rondas) + **arrays de referencias** (`check-numeric-shared-arrays.py`, diferencial Java 25) | **Sí, como subperfil** | Sin ciclos cerrados con alias publicado, sin subtipos, sin `String`, sin arrays de arrays ni primitivos compartidos |
| **A-05** Monitores e inicialización | `check-numeric-shared-monitors.py` (monitor reentrante compartido entre bytecode numérico y tareas Rayon) | **Parcial** | Falta la **política común de estáticos e inicialización perezosa** entre los dos heaps: hoy el `<clinit>` es monohilo y no se comparte |
| **A-06** Entrada Java integrada | — | **No** | Necesita la unión de programas: que una llamada Java del backend principal publique, envíe tareas y observe el estado tras `join` sin que el harness lo cablee |
| **A-07** Ruta real a `Util.makeExecutor` | — | **No** | Depende de A-06 y de B-02/B-05/B-06 (fábrica, handler, composición). `Util.makeExecutor` construye el pool desde bytecode real |
| **A-08** Repetir probe de `Main` | último intento registrado: bloqueo en `new ForkJoinPool` | **No** | Depende de A-07; sin eso el probe vuelve a morir en el mismo `new` |

**Conclusión A:** se cierran hoy **A-01 (contrato v1), A-03 y A-04 como subperfiles con límites**. A-02 queda
abierta por el 0/687, A-05 por los estáticos y A-06/A-07/A-08 porque son la cadena que lleva a `Main`.

## 4. Frente B — ForkJoinPool, workers y futures

| Tarea | ¿Qué hay de verdad? | ¿Cerrable hoy? | Qué falta exactamente |
|---|---|---|---|
| **B-01** Oráculos → contrato comprobable | `analysis/futures-contract-b01.md` (23 diferenciales, 19 guardas, 12 java-only, 21 unitarias, 8 no soportados, 7 huecos) y `check-futures-contract.py` que exige que cada guarda exista literalmente en `mc-aot/src` | **Sí** | Nada: el contrato es comprobable y falla si se rompe (así detectó mi cambio de mensaje del opt-in) |
| **B-02** Lifecycle del pool | `executor_runtime.rs` + 33 unitarias (fábrica, inicio/terminación, rechazo tras cierre, `shutdown` que no espera, pool nunca usado) | **Sí, con límite** | Sin orden global de tareas prometido ni `awaitTermination` con timeout real desde bytecode |
| **B-03** Futuros pendientes | `mark_pending_future`, `pending_future_completes_once_and_reports_state`, rechazo de objetos ajenos; desde **bytecode** solo `completedFuture` | **No** | `new CompletableFuture()` sigue rechazado al compilar: falta el ciclo de vida pendiente en el traductor, no solo en el heap Rust |
| **B-04** `get`/`join` y fallos observables | Solo el camino ya completado (`get`/`join`/`getNow`/`isDone`) | **No** | `ExecutionException`/`CompletionException`, cancelación efectiva, timeout e interrupción: ninguno existe. Medido: `cancel(true)`≡`cancel(false)` (Q-BC-3) |
| **B-05** Envío y composición | Inventario estático: 44 `completedFuture`, 36 `join`, 33 `supplyAsync`, 29 `thenApply` en 97 clases | **No** | Nada de `supplyAsync`, `thenApply`, `thenCompose`, `allOf` ni callbacks con executor |
| **B-06** Fábrica y handler de `Util` | Caracterización de `Util$2` + `TracyClient.setThreadName`; bloqueo de logger registrado | **No** | La ruta real se detiene en logging/`Exception.toString`; se cerró log4rs como «aparcado», no como resuelto |
| **B-07** Interfaz para A | `analysis/b-api-for-a.md` con superficie, propiedad, locks, fallos y 6 pruebas de frontera (`rayon_b_api.rs`) | **Parcial** | Tres decisiones siguen abiertas: `Throwable`, fuente del número de procesadores para `commonPool()`, y el opt-in unificado (mitad de A hecha, falta la de B → `Q-AB-2`) |
| **B-08** Estrés y regresiones | `rayon_stress.rs` con invariantes y timeouts; forma parte de la integral | **Sí** | Nada |

**Conclusión B:** se cierran hoy **B-01, B-02 (con límite), B-08**. B-07 queda a una decisión. B-03/B-04/B-05 son
el verdadero trabajo pendiente del frente: futuros pendientes, composición y excepciones son *capacidades*, no
pruebas que falten.

## 5. Lo que no se puede cerrar con el diseño actual (y no es cuestión de tiempo)

- **Unión de los dos programas** en un solo binario: hoy el puente enlaza heaps vía `SharedHeap` externo y el
  harness cablea ambos lados. Sin eso no hay A-06, A-07 ni A-08.
- **Estáticos y `<clinit>` compartidos**: el inicializador es monohilo; publicar estáticos exige orden y
  visibilidad entre heaps.
- **Layouts desde clases reales**: 0/687. Requiere leer el classfile oficial (parseo de campos/atributos) y no solo
  el inventario estructural.
- **Reflexión**: congelada por decisión A-C8 (límite aceptable, `reflection-gap` marcado). No cuenta como cierre.
- **GC y modelo de memoria JVM**: fuera de perfil; el heap no libera.
- **Excepciones Java reales**: Eula se detiene en `Exception.toString`; mientras eso no exista, ninguna ruta de
  error de Minecraft se puede decir «traducida».

## 6. Propuesta de cierre oficial (fase 1) y deuda declarada (fase 2)

**Fase 1 — se puede firmar hoy**, con la integral en verde (`analysis/full-regressions-a06.log`: **319 etapas,
`EXIT_STATUS=0`**, `cargo test` 66+32+34+32+33):

| Se cierra | Con esta evidencia |
|---|---|
| A-01 contrato v1 | `analysis/a01-contrato-integracion-propuesta.md` + firma pendiente de B (no bloquea el cierre del documento) |
| A-03 publicación automática (subperfil) | `check-numeric-auto-publish.py` (20 rondas, sesiones por heap, abortos) |
| A-04 mutación (subperfil) | `check-numeric-mutable-refs.py` + `check-numeric-shared-arrays.py` |
| A-05 discusión ronda 2 | `analysis/discussion/STATUS.md`, `threads/a-c.md`, `analysis/a05-round2.md` |
| B-01 contrato | `analysis/futures-contract-b01.md` + `check-futures-contract.py` |
| B-02 lifecycle (con límite) | `executor_runtime` 33 unitarias |
| B-08 estrés | `rayon_stress.rs` |

**Fase 2 — queda abierta, con dueño y dependencia**:

| Abierta | Depende de | Se cierra cuando |
|---|---|---|
| A-02 layouts reales | parseo de classfile | ≥1 clase vanilla con layout verificado (hoy 0/687) |
| A-05 estáticos | unión de programas | estáticos publicados y `<clinit>` con orden entre heaps |
| A-06 entrada Java integrada | unión de programas | llamada Java real publica y observa tras `join` sin cableado del harness |
| A-07 ruta `Util.makeExecutor` | A-06 + B-02/B-05/B-06 | el constructor real de 4 argumentos se traduce y ejecuta |
| A-08 probe de `Main` | A-07 | `Main` pasa de `new ForkJoinPool` a un bloqueo posterior, con log y hash |
| B-03 futuros pendientes desde bytecode | backend | `new CompletableFuture()` compila y completa una sola vez |
| B-04 `get`/`join`/fallos | B-03 | excepción de ejecución observable, cancelación efectiva |
| B-05 composición | B-03/B-04 | `supplyAsync`/`thenApply`/`allOf` con executor |
| B-06 `Util` fábrica/handler | logging + B-05 | factory y handler reales traducidos |
| B-07 interfaz A (cierre) | decisión de B | `Throwable`, procesadores y opt-in unificado acordados |

## 7. Cómo se verifica este documento

```sh
export JAVA_HOME=/ruta/al/jdk-25 TMPDIR=/var/tmp
grep -c '==> ' analysis/full-regressions-a06.log   # 319 etapas
tail -1 analysis/full-regressions-a06.log          # "Todas las regresiones terminaron correctamente..."
python3 mc-aot/tests/check-futures-contract.py     # el contrato de B se cae si una guarda desaparece
python3 mc-aot/tests/check-numeric-shared-arrays.py
```

Ninguna línea de este documento cambia el contador: **0 clases completas de 7.762**, `Main` bloqueado en
`new ForkJoinPool`, sin servidor nativo.
