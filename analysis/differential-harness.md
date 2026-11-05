# C-05: Differential harness — reproducible Java vs native

**Status:** design + template, no new runtime code. Counter stays 0.
**Related:** ROADMAP §5 criterion 3 (differential evidence), TODO C-05.

## Purpose

Make every `check-*` comparison reproducible: inputs, stdout/stderr, exit codes, file effects, exceptions, controlled randomness and limits saved with hashes/config; native binary must run with `java` not in `PATH`; every stub must be labeled.

## Required harness fields (checked by reviewer)

For each differential test `mc-aot/tests/check-*.py`:

- **Inputs:** fixed seed (e.g., `random.Random(263)`), explicit edge list (`-2^31`, `-1`, `0`, `1`, `2^31-1`), and `args` string built deterministically. Seed and edge list logged in output line.
- **Oracle:** Java 25 (`$JAVA_HOME/bin/java` + `$JAVA_HOME/bin/javac`) compiled to temp dir, run with `-cp` including official inner JAR (`a362...ee8ae6`). Hash of classfile under test (e.g., `ChunkStatusTasks` `7fe5...93`) printed and verified.
- **Native:** `cargo run --manifest-path mc-aot/Cargo.toml -- <fixture> <jar> <Class> <native_bin>` with timeout; native binary executed with `env -u JAVA_HOME` and `PATH` stripped of Java (`PATH=/usr/bin:/bin`) to ensure no JVM dependency. Exit code compared, not just stdout.
- **Comparison:** byte-exact `stdout` (`java.stdout == native.stdout`), `stderr` on failure, exit code `0` vs `2` for expected aborts (panic unwind → exit 2, not Java exception). For `ExecutionException`/`CompletionException` profile, `cause` identity checked per oracle contract (see `analysis/futures-contract-b01.md`).
- **Randomness:** `random.Random(seed)` with `seed` pinned; no `random.random()` unseeded. Seed documented in test docstring and log.
- **Limits:** heap limits (`10_000 objects/1_000_000 elements`) and timeouts logged; reaching limit exits with distinct code, not misreported as Java error.
- **Artifacts:** `analysis/<name>-validation.log` stored, SHA256 of log recorded in registry/manifest; `evidence_files` in `class-registry.json` pin SHA256. Re-running on clean clone must reproduce same log hash given same JDK/Rust versions (variations only in timing).

## Stub labeling rule

If a fixture uses a stub (e.g., `ChunkAccess`, logger, `Eula` provider), the log must contain `STUB:` line listing classfile hash of class under test (verified) and explicit list of stubbed collaborators:

```
OK: 80 results ... classfile hash verified; ChunkAccess, logger and others are stubs, no world integration
```

Do not claim class certification or server behavior from a stubbed run. The registry's `limitations` field must echo this.

## Template

```python
#!/usr/bin/env python3
"""<what> — differential vs Java 25, seed 263, 500 random + edges, no Java in PATH for native."""
import os, pathlib, random, subprocess, tempfile, hashlib
root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ["JAVA_HOME"]) / "bin"
jar = root.parent / "downloads/server-26.3-inner.jar"
# 1. hash classfile
# 2. compile oracle Java
# 3. build native via cargo
# 4. run both with PATH stripped for native, compare
```

Existing examples that already follow the pattern: `check-quartpos-class-surface.py` (seed 263, 500 random, PATH stripped native), `check-real-chunk-passthrough-future.py` (class hash `7fe5...93`, 80 cases, stubs labeled). New tests must copy this structure.

## Verification

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH="$HOME/.cargo/bin:$JAVA_HOME/bin:$PATH"
python3 mc-aot/tests/check-quartpos-class-surface.py            # expect exit 0, log OK
env -u JAVA_HOME PATH=/usr/bin:/bin ./mc-aot/examples/quartpos-native --help  # must not need java
python3 mc-aot/tools/check-class-registry.py
cargo test --manifest-path mc-aot/Cargo.toml
```

No hidden `JAVA_HOME` during native run — CI must enforce this by running native stage with `PATH` filtered.

## What C-05 does NOT do

- Does not claim full-domain proof — sample + directed limits only.
- Does not change translation — harness is test-only.
- Does not lift `log4rs` park or promise server start.

