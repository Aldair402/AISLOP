# D-01: Resources and environment — inventory for 26.3

**Status:** inventory, no server claim. Counter 0.
**Branch:** `trabajo/d-01-resources`
**Date:** 2026-11-05
**Base:** inner JAR `a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6`, 7762 classes, 39 bundled libs (22905 classes) per `dependency-summary.json`.

## 1. Classpath

- **Inner JAR:** `downloads/server-26.3-inner.jar` SHA256 `a3621...ee8ae6` — contains 7762 classes, `net/minecraft/server/Main` root.
- **Static closure from Main:** 7253 inner classes + 643 bundled libs + 451 JDK-like prefixes = 8347 unique references. Not proof of runtime, includes unused branches.
- **Outer bundle:** `server-26.3.jar` SHA1 `33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c` (60M) — contains `META-INF/versions/26.3/server-26.3.jar`.
- **Resources verified in code:** `Class.getResourceAsStream("/version.json")` only for `DetectedVersion` (present/absent, read/EOF/close 100 ops OK), `ClassLoader.getResources` for `StaticLoggerBinder.class` and `META-INF/log4j-provider.properties` (absent/URL 100 ops OK). Other resources abort — per `numeric.rs` guards `STATIC_BINDER_PRESENT`/`LOG4J_PROVIDER_ABSENT` + `MC_AOT_CLOSED_CLASSPATH=1`.

## 2. Filesystem

- **Current profile:** `Path.of("x",..)` / `Paths.get` supported for single segment, not full I/O. Real `Files` ops are guarded, not general FS. `eula.txt` handling lives in D-02, not here.
- **Working dir:** isolated `mktemp` per C-07 probe — no persistent world before Main compiles.
- **Limits:** heap 10_000 objects / 1_000_000 elements per run, no GC.

## 3. Configuration & properties

- **Properties read:** `System` line separator, `MC_AOT_JAVA_PROCESSORS` required for `availableProcessors` (must equal `-XX:ActiveProcessorCount`), `AsyncLogger.ThreadNameStrategy` affects `Enum.valueOf` branch but not executed by default.
- **JFR/Tracy:** `MC_AOT_DISABLE_JFR=1` opt-in equals `-XX:-FlightRecorder`; active JFR/Tracy not supported (probe logs `main-latest-captured-attempt.log`).
- **Config files:** `server.properties`, `eula.txt`, world files not parsed yet — guarded as `FileNotFoundException` profile (120 ops).

## 4. Locale, timezone, charset

- **Locale:** only `Locale.ROOT` supported (`toUpperCase/toLowerCase` ASCII only, 65k exhaustive `Character.isWhitespace/toUpper` ok). `ofPattern "yyyy-MM-dd HH:mm:ss"` + `Locale.ROOT` for `CrashReport` DateTimeFormatter — other patterns/locales abort.
- **Charset:** UTF8 via `StandardCharsets.UTF_8` (`utf8_charset` singleton), no other charsets.
- **Timezone:** not modeled — `Date.toInstant` roundtrip 214 cases with i64 extremes, but `withZone/ofPattern` outside profile abort.

## 5. Network

- **Required by Main after startup:** listen on `25565` (default) — but C-07 probe **never opens ports** (`main-probe.sh` mktemp, no `eula=true`). Future D-04 will test local `127.0.0.1` with authorized client only.
- **Protocol:** 630 `net.minecraft.network.*` classes — guarded, no real sockets yet.

## 6. Effects and errors contrasted

- **Validated differentials:** 100 version.json, 100 StaticLoggerBinder/log4j-provider, 110 `availableProcessors`, 80 `System.currentTimeMillis` (window), 65k `isWhitespace/toUpper`.
- **Guarded aborts:** unknown resource → `error("recurso fuera del perfil")`, missing `JAVA_PROCESSORS` → abort, not silent.

## Repro

```sh
python3 mc-aot/tools/check-version-resource.py # 100 ops
python3 mc-aot/tools/check-classloader-resources.py # 100 ops
cat analysis/dependency-summary.json
```

No change to counter; next is D-02 Eula (blocked at `Exception.toString`) and D-03 logging (parked).
