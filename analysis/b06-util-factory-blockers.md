# B-06 — Por qué `Util.makeExecutor` sigue sin modelarse

**Tarea:** B-06 de [`TODO.md`](../TODO.md) · **Fecha:** 2026-11-05
**Estado:** **bloqueada**, con el bloqueo caracterizado a nivel de bytecode. No se ha escrito código de relleno:
cualquier implementación hoy tendría que inventar el resultado de las llamadas de log.

Los datos de esta nota salen del JAR oficial (`server-26.3-inner.jar`, SHA-1 `33680f5f…`) con
`javap -p -c`, sobre `net/minecraft/util/Util.class` y `net/minecraft/util/Util$2.class`.

---

## 1. Qué hace realmente `makeExecutor(String name)`

```
n = Mth.clamp(Runtime.availableProcessors() - 1, 1, getMaxThreads())
if (n > 0)  →  new ForkJoinPool(n, <factory lambda>, <handler lambda>, /*async*/ true)
            →  new TracingExecutor(anterior)
else        →  MoreExecutors.newDirectExecutorService()   (rama inalcanzable: el clamp tiene mínimo 1)
```

`getMaxThreads()` lee la propiedad `-Dmax.bg.threads`; si el valor entero no cae en `1..255`, avisa por log y
usa el valor por defecto.

**Hallazgo útil para B-02:** el `clamp(…, 1, …)` de Minecraft es exactamente el motivo por el que el perfil
declara `paralelismo fuera del perfil 1..255`. El límite no es arbitrario del adaptador: es el del juego, y
coincide con su propia validación de `max.bg.threads`.

**Hallazgo útil para B-02 (2):** la rama de Guava (`newDirectExecutorService`) es **inalcanzable** con el clamp
actual, así que no hay que modelar `MoreExecutors`.

## 2. Las tres cosas que impiden traducirlo

| # | Elemento observado en el bytecode | Por qué bloquea | Qué haría falta |
|---|---|---|---|
| 1 | `invokedynamic … newThread:(String, AtomicInteger)ForkJoinPool$ForkJoinWorkerThreadFactory` y `lambda$makeExecutor$0` que devuelve `new Util$2(pool, nombre, base)` | La factory no es una función trivial: crea una **subclase** de `ForkJoinWorkerThread` con estado capturado. Hoy el adaptador la rechaza (`factory personalizada requiere un worker y async=true`, `worker con override run/start no soportado`) | Ampliar el perfil de `ForkJoinWorkerThread` a una subclase con `onStart`/`onTermination`, o aceptar la factory solo por su efecto de nombrado |
| 2 | `onStart()` llama a `TracyClient.setThreadName(nombre, nombre.hashCode())` **antes** de `super.onStart()` | Depende de Tracy, que el proyecto no modela | El opt-in `MC_AOT_RAYON_ASSUME_NO_TRACY` ya existe, pero hoy solo cubre el caso de no llamar; aquí la llamada es obligatoria en el camino real |
| 3 | `onTermination(Throwable)` registra `"{} died"` (warn) o `"{} shutdown"` (debug) con un `Logger` de **slf4j** | Es exactamente la decisión de logging que el proyecto tiene **aparcada** (`log4rs` en `TODO.md`) | Que se decida el backend de logging. Sin él, modelar `onTermination` obligaría a inventar la salida |

A eso se suma, del mismo camino, `com.mojang.jtracy.TracyClient` (clase del bundle) y el envoltorio
`TracingExecutor`, que ya están cubiertos por `check-real-tracing-shutdown.py` y sus opt-ins
`MC_AOT_RAYON_ASSUME_NO_INTERRUPT` / `MC_AOT_RAYON_ASSUME_NO_TRACY`.

## 3. Comportamiento actual, verificado

Ante un programa que construye el pool como lo hace Minecraft, el generador **no inventa**: rechaza.

- `factory personalizada requiere un worker y async=true` — cualquier `ForkJoinPool(int, factory, handler, boolean)`
  con factory no trivial;
- `factory Java no trivial` — factory que no se resuelve a un patrón conocido;
- `handler personalizado no soportado` — el handler de `uncaughtException` de Minecraft.

Estas guardas están cubiertas por `check-rayon-forkjoin-profile.py` y sus casos en el contrato B-01; no hace
falta añadir nada para que el rechazo sea verificable.

## 4. Propuesta de desbloqueo en dos pasos

1. **B-06a (no depende de nadie):** admitir la factory **solo por el nombrado** — `nombre + contador`, con el
   contador como `AtomicInteger` del heap — y declarar explícitamente que `onStart`/`onTermination` no se
   ejecutan (`worker con override run/start no soportado` se convierte en un aviso del generador, no en un
   rechazo). No cambia la semántica observable de las tareas; sí cambia los nombres de hilo, y eso hay que
   declararlo en la evidencia.
2. **B-06b (depende de la decisión de logging):** ejecutar `onTermination` contra el backend de logging que el
   proyecto elija, y solo entonces modelar `TracyClient` (o ampliar el opt-in para declarar su ausencia).

Ninguna de las dos debe hacerse antes de que B-04 cierre el modelo de fallos: `onTermination(Throwable)` recibe
precisamente lo que hoy no sabemos representar.

## 5. Lo que esta nota **no** afirma

- No afirma que Minecraft use `Util.makeExecutor` en la ruta que se traduce hoy: no se ha medido.
- No afirma equivalencia de nombres de hilo ni de trazas: no se pueden comparar sin el backend de logging.
- No propone sustituir el `ForkJoinPool` real por un pool propio «equivalente»: eso sería un stub, y el proyecto
  no los admite sin etiquetar.
