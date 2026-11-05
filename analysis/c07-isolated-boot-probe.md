# C-07: Isolated boot probe

**Branch:** `trabajo/c-07-isolated-boot-probe`
**Tool:** `mc-aot/tools/main-probe.sh`
**Status:** script added, no binary claimed, no EULA accepted.

## Guarantees

- Runs in `mktemp` under `$TMPDIR/mc-main-probe.XXXXXX`, logs to `analysis/main-probe-*.log`, then removes workdir — no leftover world.
- **Never** writes `eula=true`, never opens `25565` or any port by default. Logs state `eula=false` would be needed for any future manual test.
- Cleans previous `mc-aot/target/debug/mc-aot` and `work/native-main` before compile — a prior success cannot be mistaken for current success.
- Records `JAR_SHA256`, `JAVA_HOME`, `RUST` versions, and `compile_exit` explicitly.

## Current blocker (reproduced 2026-11-05)

```
Error: new no soportado: java/util/concurrent/ForkJoinPool
  al compilar net/minecraft/util/Util.makeExecutor(...)TracingExecutor;
  al compilar net/minecraft/util/Util.<clinit>()V
  ...
  al compilar net/minecraft/server/Main.main([Ljava/lang/String;)V
compile_exit=1
```

Same as `analysis/main-completed-future-attempt.log`. No binary produced — expected until B-06/B-07 + A-07 integration.

## Manual future cycle (prepared, not executed)

When blocker is resolved, the planned manual steps (require human approval each time) are:

1. `mkdir -p work/server && echo "eula=false" > work/server/eula.txt` — reviewer must set `true` manually.
2. Run native with temp world: `work/native-main --nogui --world work/server` — verify `Done`, listen, then immediate `stop`.
3. Test save/load, restart — all with client authorized, local port only, backup any real world.

This document keeps `count_complete=0`; a boot does not count as class completion.

## Verification

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH="$HOME/.cargo/bin:$JAVA_HOME/bin:$PATH"
bash mc-aot/tools/main-probe.sh
grep compile_exit analysis/main-probe-*.log
```

Cargo test must still pass — this change adds no Rust code.

