# A-05 · Ronda 2 de la discusión: dos huecos reales cerrados con código

**Rama:** `trabajo/a-05-round2-publish-scope` · **Base:** `main` `8d21505` (rebase de A-04 encima) · **Fecha:** 2026-11-05
**Autor:** MIlaSoraki &lt;mila.gastelum@autistici.org&gt;

C abrió tres preguntas a A al cerrar la ronda 1 (Q-AC-6, Q-AC-7, Q-AC-8). Este informe responde con código y
mediciones, no con prosa, y abre las tres preguntas que la regla 7 obliga a A (`Q-AB-1`, `Q-AB-2` a B; `Q-AC-5` a C).

## 1. Punto de partida medido

| Hecho | Estado antes de A-05 |
|---|---|
| `trabajo/a-04-mutable-refs` (`e8ee625`) | rebasado sobre `main` `8d21505` sin conflictos lógicos; solo `TODO.md` |
| `check-numeric-mutable-refs.py` sobre el `main` nuevo | en verde (20 rondas) |
| `check-numeric-auto-publish.py` sobre el `main` nuevo | en verde |
| `cargo test` | 66 + 32 + 34 + 32 + 33 |
| Integral de `main` `8d21505` sola | **en rojo** en `check-class-surface-evidence` (ver §4) |
| Clases completas | **0 de 7.762** |

## 2. Q-AC-6 · `PUBLISH_ACTIVE` deja de ser una casilla global

El diagnóstico de C era correcto y el hueco era real: con dos sesiones en dos hilos y dos heaps, la segunda
sobrescribía la marca global y un worker del primer heap caía en el `return` silencioso —justo lo que Q-AC-2 pedía
cerrar.

**Cambio** (`mc-aot/src/numeric_runtime.inc`): `static PUBLISH_ACTIVE: Mutex<Vec<(usize, ThreadId)>>`, es decir un
registro **por heap** (clave = puntero del `bridge_owner`), con `publish_active_insert`,
`publish_active_remove` y `publish_active_owner_of`. `Vec` en vez de `HashMap` solo por poder inicializarlo en un
`static`; la semántica es la del mapa que pedía C. La guarda `PublishSessionGuard` borra **solo su entrada**.

| Caso | Comportamiento | Prueba |
|---|---|---|
| Dos sesiones, hilos y heaps distintos | conviven | `sessions_on_different_heaps_coexist` |
| Segunda sesión sobre el **mismo** heap desde otro hilo | `publicación: sesión ya activa para este heap` | ídem |
| Segundo `install` en el **mismo** hilo | `publicación: sesión ya instalada` (sin cambios) | `bytecode_allocations_are_published_automatically` |
| Publicar desde un hilo sin sesión de ese heap **con otra sesión viva en otro hilo** | aborta, `publicación: hilo distinto al de la sesión`, exit 2 | `publishing_from_a_different_thread_is_fatal` |
| Cerrar una sesión | no borra la de otro heap | las anteriores |

No se declaró «una sola sesión por proceso»: el servidor real necesitará varios puentes y un límite falso habría
trasladado el problema a B. Sigue siendo **una sesión por hilo y por heap**.

## 3. Q-AC-7 · Opt-in unificado de futuros: A es dueño y su mitad ya está hecha

`mc-aot/src/numeric.rs` gana `futures_optin()`:

- `MC_AOT_FUTURES=completed-only` enciende el perfil;
- `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` sigue valiendo como alias por una versión;
- un valor desconocido **se rechaza** (`MC_AOT_FUTURES: valor no soportado: <valor>`) y no genera binario;
- los tres puntos que leían la variable (dos guardas y la clasificación de `checkcast/instanceof`) pasan por la
  función, así que no queda una cuarta lectura escondida.

Mensaje único: `CompletableFuture: requiere MC_AOT_NUMERIC_COMPLETED_FUTURE=1 (o el nombre unificado
MC_AOT_FUTURES=completed-only)`. El literal viejo se conserva en medio a propósito: `check-futures-contract.py`
(B-01) exige esa cadena exacta en `mc-aot/src`, y romperla habría sido cambiar el contrato de B de tapadillo. La
integración completa llega cuando B añada su mitad (`Q-AB-2`).

`check-numeric-completed-future.py` comprueba además: binario generado **solo** con el nombre nuevo, 90 resultados
idénticos a Java 25, y rechazo del valor desconocido (`analysis/a05-completed-future.log`).

**Pendiente de B** (`Q-AB-2`): el mismo `futures_optin()` y el mensaje literal con `MC_AOT_RAYON_COMPLETED_FUTURE`
en los 7 sitios de `mc-aot/src/concurrent_compile.rs`. Dueño del PR conjunto: A, rama
`trabajo/a-06-opt-in-futuros`, **fecha objetivo 2026-11-07**; si B no confirma, sale con el alias de A y un `TODO`
explícito en el lado de B.

## 4. Hallazgo: `main` `8d21505` estaba en rojo

La integral se detuvo en `check-class-surface-evidence`: la prueba esperaba `methods_without_evidence == ['<init>()V']`
mientras `analysis/class-evidence/quartpos.json` ya declara evidencia para el constructor privado (la medición de
reflexión en Java). A no revirtió la evidencia de C: actualizó la tupla a `(7762,6,6,4,4,False,[])`, dejó escrito
que **el inventario no distingue evidencia diferencial de evidencia solo-Java** —por eso `certified: false` sigue
siendo la única lectura honesta— y corrigió el mensaje final, que decía «5/6 métodos». La etapa pasa
(`analysis/a05-class-surface-evidence.log`). Se avisa a C en Q-AC-5.

## 5. Q-AC-8 · Reflexión: límite aceptable, con tres condiciones

1. Solo puede excluirse de una clase lo **inalcanzable sin reflexión**; un miembro que el programa real invoca por
   reflexión deja la clase en `partial-evidence` con motivo `reflection-gap`.
2. La evidencia **solo-Java** se etiqueta y no certifica: el `<init>` privado de `QuartPos` sigue en `java-only`,
   `certified: false`.
3. La **puerta de arranque manda** sobre el contador: `Main` sigue bloqueado en `new ForkJoinPool`, y ninguna clase
   con `reflection-gap` puede desbloquearlo. Si `Main` necesitara reflexión real, entonces se abre el subperfil
   mínimo (`getDeclaredConstructors` + `newInstance` con y sin `setAccessible`) con su propio diferencial.

## 6. Lo que NO cambia

- **0 clases completas certificadas** de 7.762; mitad en 3.881.
- `Main` sigue detenido en `new no soportado: java/util/concurrent/ForkJoinPool`.
- Sin arrays de referencias, `String`, subtipos, estáticos publicados, GC ni unión de programas.
- El backend concurrente sigue rechazando campos de referencia no `final` (`Q-AB-1`): lo que se probó es el puente
  numérico, no Rayon.
- Sigue habiendo harness opt-in, no servidor.

## 7. Reproducir

```sh
export JAVA_HOME=/ruta/al/jdk-25 TMPDIR=/var/tmp
python3 mc-aot/tests/check-numeric-auto-publish.py      # sesiones por heap, abortos, 20 rondas
python3 mc-aot/tests/check-numeric-completed-future.py  # opt-in unificado + 90 resultados
python3 mc-aot/tests/check-numeric-mutable-refs.py      # A-04 sobre el main nuevo
python3 mc-aot/tests/check-class-surface-evidence.py    # etapa que estaba en rojo
cargo test --offline --manifest-path mc-aot/Cargo.toml
bash mc-aot/run-regressions.sh                          # integral; necesita JAVA_HOME y TMPDIR=/var/tmp
```

Logs de esta ronda: `analysis/a05-*.log` y la integral `analysis/full-regressions-a05.log`.
