# minecraft-aot

**Minecraft Java → binario nativo (experimental).** Compilador AOT experimental que traduce el bytecode del servidor oficial de Minecraft
(`server.jar` 26.3 de Mojang) a Rust y de ahí a ejecutables nativos, con **Java 25 como
oráculo diferencial** para validar cada perfil traducido. No es un servidor funcional
ni certifica nada por sí mismo: cada resultado se contrasta caso a caso contra una JVM
real antes de considerarse evidencia.

> **Estado honesto (2026-11-07):** el servidor **no arranca**. Hay **1 de 7.762 clases
> completas certificadas** (`net/minecraft/world/flag/FeatureFlagUniverse`, firmada por
> A el 2026-11-07 sobre evidencia de C; el contador no se puede auto-incrementar sin el
> gate). `QuartPos` sigue `review-required` y `TickThrottler` está medido pero marcado
> `review-required`: **ninguno** de los dos incrementa el contador. Meta del proyecto:
> 3.881 clases completas.

## Qué es (y qué no es)

- **Es**: una traductora bytecode→Rust por perfiles acotados, un runtime numérico
  simulado, oráculos diferenciales Java 25 → binario y una suite de regresión integral.
- **No es**: un servidor de Minecraft, un intérprete JVM general, ni un sustituto de
  la JVM. Las rutas no verificadas **abortan explícitamente** en lugar de simular
  comportamiento. Ningún diferencial parcial equivale a certificar una clase.
- **No distribuye**: los JAR de Mojang, los descompiladores ni el JAR del servidor
  descompilado. Quien quiera reproducir debe descargar los artefactos oficiales.

## Estado actual

| Aspecto | Estado |
| --- | --- |
| Clases completas certificadas | **1/7.762** (`FeatureFlagUniverse`) |
| Evidencia registrada | `analysis/class-registry.json` (gate: `mc-aot/tools/check-class-registry.py`) |
| Arranque del servidor | No arranca; `Main` bloqueado en `ForkJoinPool` |
| Suite integral de referencia | **334 etapas, exit 0** — `analysis/full-regressions-a12.log` (post-limpieza, sobre este árbol; `analysis/full-regressions-a11.log` es la referencia previa) |
| Futuros | Opt-in `MC_AOT_FUTURES=restricted` (solo futuros ya completados normalmente; `completed-only` es alias histórico) |
| Rayon | Prototipo desconectado del backend principal |
| log4rs | Aparcado (ver `PLAN-ARRANQUE.md`); no se simula logging |
| CI | `.github/workflows/ci.yml` — jobs `quick` (cargo + registry), `focused` (oráculos Java, sin la suite completa) y `full` (solo manual) |

El criterio de «clase completa» exige revisión y evidencia reproducible; ninguna clase
se auto-certifica. Ver `ROADMAP.md` (objetivo y fases) y `analysis/class-registry.json`.

## Requisitos

- **JDK 25** (Temurin) — `JAVA_HOME` apuntando a él.
- **Rust / Cargo** (toolchain stable).
- **Python 3** (los checks diferenciales y el gate están en Python).
- `curl`, `sha1sum`, `sha256sum`, `git`.

## Descarga de los artefactos oficiales

El repositorio no incluye los JAR de Mojang. Descárgalos de la fuente oficial y
verifica su integridad **antes** de usarlos:

```sh
mkdir -p downloads
curl -fL https://piston-data.mojang.com/v1/objects/33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c/server.jar -o downloads/server-26.3.jar
printf '%s  %s\n' 33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c downloads/server-26.3.jar | sha1sum -c -
python3 - <<'PYCODE'
import pathlib, zipfile
with zipfile.ZipFile('downloads/server-26.3.jar') as z:
    pathlib.Path('downloads/server-26.3-inner.jar').write_bytes(z.read('META-INF/versions/26.3/server-26.3.jar'))
PYCODE
printf '%s  %s\n' a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6 downloads/server-26.3-inner.jar | sha256sum -c -
```

## Reproducir

```sh
# prepara JAVA_HOME y PATH (hace falta el JDK 25)
source ./mc-toolchain.sh

# reconstruye los ejecutables de ejemplo (se sobrescriben; no van al repo)
bash mc-aot/build-examples.sh

# suite integral: 58+25 pruebas Rust, diferenciales Java 25 ↔ binario y los
# checks de gate. Tarda ~35 min. Los .log -latest son evidencia regenerable.
bash mc-aot/run-regressions.sh
```

La suite **no certifica** clases ni el arranque del servidor; es la condición mínima
para que un cambio sea considerado no-regresivo.

## Estructura del repositorio

| Ruta | Contenido |
| --- | --- |
| `mc-aot/` | El compilador AOT: crate Rust (`src/`), tests diferenciales Python (`tests/`), `build-examples.sh`, `run-regressions.sh`, `ci/` y el prototipo `log4rs-prototype/` |
| `graal-test/` | Programas Java de referencia usados como oráculo diferencial |
| `analysis/` | Evidencia: `class-registry.json` y `class-evidence/*.json` (gate), contratos (`a01-contrato-integracion.md`, `futures-contract-b01.md`), baseline (`c01-baseline-2026-11-05.md`) y registros de corridas aprobadas |
| `scripts/` | Utilidades (p. ej. `decompile-cfr.sh`) |
| `tools/` | Metadatos de herramientas (los JAR no se distribuyen) |
| `mc-toolchain.sh` | Exporta `JAVA_HOME` y PATH del JDK 25 |
| `TODO.md` | Tablero de trabajo del equipo (tareas activas, IDs, reparto) |
| `ROADMAP.md` | Roadmap del proyecto (fases y criterio de clase completa) |
| `PLAN-ARRANQUE.md` | Plan detallado de arranque (estado por frente) |

## Flujo de trabajo

- Ramas `trabajo/*` para el trabajo en curso; nada se empuja directo a `main` y los
  cambios entran por revisión. Los commits llevan la identidad del autor.
- Cualquier afirmación sobre clases, perfiles o el servidor requiere **evidencia
  reproducible** (tests diferenciales, logs de corridas, registros en
  `class-registry.json`). No se acepta «funciona en mi máquina».

## Aviso legal

Minecraft y los archivos del servidor son propiedad de Mojang Studios. Este proyecto
no está afiliado ni respaldado por Mojang. Los artefactos del juego no se distribuyen
en este repositorio; quien los descargue debe revisar y aceptar la EULA correspondiente
por su cuenta. No se ha aceptado ninguna EULA en la elaboración de este trabajo. El
código propio del repositorio no declara licencia de uso por ahora: consúltalo antes de
reutilizarlo.
