# Frente B — estado para el equipo

**Rama:** `trabajo/b-01-contrato-futures` · **Último commit:** `3a341fc` (pusheado a `deploy`)
**Base:** `documentacion/todo-colaboracion-8fa1893` · **Fecha:** 2026-11-05
**Ronda 3 de la discusión:** B respondió Q-AB-1 (referencias mutables: opt-in aceptado con orden campos→monitor) y Q-AB-2 (opt-in unificado: `MC_AOT_FUTURES=restricted`), cerró Q-BC-8/9/10 y abrió Q-BA-1 y Q-CB-1. Hilo: `analysis/discussion/threads/a-b.md`, `b-c.md`.

**Identidad:** todos los commits van firmados como `MIlaSoraki <mila.gastelum@autistici.org>`, con el estilo de asunto de `main` (una línea, inglés, imperativo). El trabajo lo ejecuta un agente; queda declarado aquí y en `review-answers-from-b.md`.

**Resumen:** de las ocho tareas de B, **cuatro están cerradas** (B-01, B-02, B-07, B-08), **una tiene su primer
subperfil funcionando** (B-03) y **tres están bloqueadas por decisiones que no son de B** (B-04, B-05, B-06).
Ninguna tarea se ha cerrado con supuestos disfrazados: lo que no se puede modelar hoy se rechaza con un mensaje
literal y verificable.

---

## 1. Tablero

| Tarea | Estado | Evidencia | Qué falta y de quién depende |
|---|---|---|---|
| **B-01** Contrato comprobable | **Hecha** (revisión de C pendiente) | `analysis/futures-contract-b01.{md,json}` (83 casos), `check-futures-contract.py`, 3 oráculos a 40 rondas | Que C confirme los tres registros en `run-regressions.sh` |
| **B-02** Lifecycle y perfil del pool | **Hecha** | `check-rayon-java-pool-queries.py`, `rayon_pool_queries.rs`, `analysis/b02-futures-suite-jdk25.log` | Nada de B; el 4-arg del constructor con factory depende de B-06 |
| **B-03** Futuros pendientes | **Subperfil 1 hecho** | `check-rayon-pending-future.py` (48 resultados Java 25), 3 pruebas de heap/runtime | Fallo (`completeExceptionally`) y cancelación efectiva: **decisión de A** (modelo de `Throwable`) |
| **B-04** `get`/`join` y fallos | **Bloqueada por decisión** | oráculo `fjp-handler` + casos `err.*` ya fijan la semántica Java | Representación de `Throwable` acordada con A |
| **B-05** Composición | **Bloqueada por B-04** | prioridad fijada por rutas comprobadas | `submit(Callable)`/`supplyAsync` necesitan la forma de lambda con valor y el modelo de fallos |
| **B-06** Factory y handler de `Util` | **Bloqueada, con causa medida** | `analysis/b06-util-factory-blockers.md` (bytecode real) | Decisión de logging (aparcada) y `onTermination(Throwable)` → depende de B-04 |
| **B-07** Interfaz para A | **Entregada + opt-in unificado** | `analysis/b-api-for-a.md`, `rayon_b_api.rs` (6 pruebas de frontera) | A debe aceptar las tres decisiones abiertas de su §6 |
| **B-08** Estrés y regresiones | **Hecha** | `rayon_stress.rs`, 5 pruebas de invariantes con perro guardián | Que C la incorpore a la integral |

## 2. Qué tiene que hacer C al unificar

1. **`run-regressions.sh`**: las cuatro entradas de B ya están escritas y pendientes de tu confirmación —
   `check-forkjoin-handler-oracle`, `check-futures-contract`, `check-rayon-java-pool-queries` y
   `check-rayon-pending-future` (líneas 46–49, junto a las ocho pruebas de concurrencia que ya estaban).
   El script tiene hoy 156 entradas; ninguna se ha eliminado.
2. **No meter en la suite** `rayon_pool_queries`, `rayon_stress` ni `rayon_b_api`: son pruebas de `cargo test`
   (integración), y la regla del proyecto dice que la suite solo cuenta con `exit 0` de scripts `.py`.
   Ya se ejecutan solas con `cargo test`.
3. **Duplicados a resolver**: el opt-in de futuros existe en dos variables (`MC_AOT_RAYON_COMPLETED_FUTURE` y
   `MC_AOT_NUMERIC_COMPLETED_FUTURE`) y dos mensajes distintos (`gap.two-optins`); el contrato B-01 los documenta
   como hueco, no como equivalencia.
4. **Evidencia**: `analysis/b02-futures-suite-jdk25.log` y `analysis/b03-b08-futures-suite-jdk25.log` son logs
   focalizados, no la integral. No los sobrescribas al correr la integral.

## 3. Decisiones que necesita A (bloquean B-04/B-05/B-06)

| Decisión | Por qué la necesita B | Consecuencia si no se toma |
|---|---|---|
| Representación de `Throwable` y de un fallo de tarea | B-04 debe distinguir `ExecutionException` / `CompletionException` / relanzado directo, y B-03 debe poder fallar un futuro | Un fallo sigue abortando el proceso con diagnóstico; no se inventan excepciones |
| `commonPool()` con identidad compartida | Lo pide `ForkJoinPool.commonPool()` en código real | Sigue rechazado con mensaje literal |
| Un solo opt-in de futuros | Hoy hay dos interruptores para el mismo concepto | Dos rutas de generación distintas, documentadas como hueco |
| Backend de logging (proyecto: `log4rs` aparcado) | B-06 debe ejecutar `onTermination` que registra por slf4j | `Util.makeExecutor` sigue rechazado |

## 4. Pruebas ejecutadas en este entorno (Rust 1.99.1, Temurin 25.0.5)

| Comando | Resultado |
|---|---|
| `cargo test` (5 binarios) | **66 + 32 + 34 + 32 + 33 = 197 pruebas, 0 fallos** |
| Suite focalizada B (15 scripts `.py`, JDK 25) | **15/15 OK** — log `analysis/b03-b08-futures-suite-jdk25.log` |
| **Integral completa** `bash mc-aot/run-regressions.sh` | **exit 0, 310 etapas**, «Todas las regresiones terminaron correctamente» — `analysis/full-regressions-b-frente-contrato-futures-retry3.log` |
| `check-futures-contract.py` | exit 0: cada diferencial cita un test de la suite, cada guarda existe literalmente, cada unitaria existe, documento y JSON no divergen |
| Contrato | 83 casos: 23 diferenciales, 19 guardas, 21 unitarias, 12 solo-Java, 8 sin modelar; 3 oráculos; 7 huecos |

## 5. Lo que este frente **no** afirma

- No afirma equivalencia general con `java.util.concurrent`: cada diferencial es un caso concreto contra JDK 25,
  y las muestras no se extrapolan.
- No afirma que Minecraft use hoy las clases admitidas en la ruta que se traduce: la cobertura real es de A-07.
- No convierte límites de Rust ni panics en excepciones Java: los rechazos son mensajes literales del generador.
- No hay stubs sin etiquetar: los tres documentos de bloqueo (`b06-…`, §6 de `b-api-for-a.md`, huecos del contrato)
  dicen exactamente qué falta y quién lo desbloquea.

## 6. Commits de B en la rama

| Commit | Contenido |
|---|---|
| `7ddab1f` | B-01: contrato comprobable de ForkJoinPool, lifecycle y futuros |
| `ed7ca91` | B-02: consultas de lifecycle del pool restringido con diferencial Java 25 |
| `f4aa12d` | B-01: oráculos ampliados con `submit(Callable)`, `invoke`, `commonPool` y contadores |
| `7f6d039` | B-03/B-08: futuro pendiente con completado normal y estrés de invariantes |
| `3a341fc` | B-07: interfaz de concurrencia para A; B-06: bloqueo caracterizado |

`git diff --stat` contra la base: 22 archivos, +3230 / −29.

## 7. Nota de entorno para reproducir la integral

En esta máquina `/tmp` es un `tmpfs` de 992 MB. La integral construye varios `target` de Cargo que suman más de
900 MB, así que con el `TMPDIR` por defecto muere con `Error: No space left on device (os error 28)`; el primer
síntoma puede aparecer como un fallo de compilación ajeno al cambio (nos pasó en `compare-small-args`).

Lo que sí funciona, y con lo que se obtuvo el registro `analysis/full-regressions-b-frente-contrato-futures-retry3.log`:

```sh
export PATH=$HOME/.cargo/bin:$PATH
export JAVA_HOME=/ruta/al/jdk-25
export TMPDIR=$HOME/.cache/tmp     # fuera del tmpfs
unset CARGO_TARGET_DIR             # la auditoría busca el binario en mc-aot/target/release
mkdir -p "$TMPDIR"
bash mc-aot/run-regressions.sh > analysis/full-regressions-MI-TAREA.log 2>&1
```

No fijar `CARGO_TARGET_DIR` es obligatorio: `graal-test/audit.py` busca `target/release/mc-aot` y aborta con
«No se encontró el ejecutable de mc-aot en target/release» si el binario se compiló en otro sitio.
Los tres intentos fallidos quedan en `analysis/full-regressions-b-frente-contrato-futures{,retry,retry2}.log`,
sin sobrescribir nada, porque una ejecución interrumpida no se presenta como aprobada.
