# C-08b: Integrate A-02/A-03 numeric bridge into regression suite

**Branch:** `trabajo/c-08b-integration-a03` · **Base:** `trabajo/c-08-integration-release` (802bff3) + `trabajo/a-01-contrato-heap` (724f15d)
**Date:** 2026-11-05 · **JDK:** 25.0.5+8 · **Rust:** 1.99.1 · **Jar:** `downloads/server-26.3.jar` (SHA-1 `33680f5f`)
**Counter:** `count_complete=0` — no new class certified; A-03 is opt-in harness, not Main.

## What was integrated

Cherry-picked from A `724f15d` without ROADMAP/TODO changes:

- `mc-aot/src/numeric_runtime.inc` — `PublishSink` trait + `install_publish_session`/`clear_publish_session` (thread-local). `object_new` publishes `SharedObj` at construction if sink admits the class. Cross-heap publish aborts with `publicación: otro heap numérico` (exit 2). Double-install rejected with `publicación: sesión ya instalada`.
- `mc-aot/src/numeric_concurrent_graph_bridge.inc` — `NumericGraphBridge::install` installs sink from validated layouts; `lookup` returns `ObjectId` without passing layouts. Manual `attach` preserved for earlier differentials.
- `mc-aot/tools/numeric_bridge_layout.py` — classfile validator (164 lines): distinguishes `int` vs `byte`/`char`/`short`/`boolean`, final refs, exact classes, rejects layouts with wrong hashes/types/flags.
- `mc-aot/tests/check-numeric-bridge-layout.py` — 2 cyclic layouts + empty + reverse order + 26 rejections; synthetic javac classfiles; cargo build verification; no Main.
- `mc-aot/tests/check-numeric-auto-publish.py` — harness installs session with generated layout, runs translated `<clinit>` and `fresh(int)`; root/child + fresh objects auto-published; 4 ForkJoinPool tasks update shared object under monitor; value matches Java 25. Guards: duplicate session, out-of-profile class, close stops new publishes without breaking published, foreign-heap abort.
- `mc-aot/run-regressions.sh` — added 2 lines after `check-numeric-concurrent-graph-ticktask`:
  ```
  run_logged check-numeric-bridge-layout python3 mc-aot/tests/check-numeric-bridge-layout.py
  run_logged check-numeric-auto-publish python3 mc-aot/tests/check-numeric-auto-publish.py
  ```

No change to `C-01..C-07` artefacts, `class-registry`, `family-partition`, or `main-probe.sh`.

## Verification (focal, on this branch)

```
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH="$HOME/.cargo/bin:$JAVA_HOME/bin:$PATH"
cargo test --manifest-path mc-aot/Cargo.toml              # 60 + 26 OK
python3 mc-aot/tests/check-numeric-bridge-layout.py       # OK: 2 layouts cíclicos, 26 rechazos; no Main
python3 mc-aot/tests/check-numeric-auto-publish.py        # OK: 20 rondas Java/Rust, 20 valores, 4 guardas + 4 tasks
```

Both A checks rely on `cargo build --offline`; the first full `cargo test` populated the rayon offline cache, so no `--offline` fetch failure.

## Limits and vigilance notes (from A, preserved)

- Session is per-thread; workers read-only, worker allocations not published.
- Only ordinary objects in layout profile; no statics, `<clinit>` sharing, arrays, String, subtypes, reference writes.
- `SharedHeap`/layouts/program union remain harness-owned; `Main` still blocked on `new ForkJoinPool`.
- `object_new` publishes before constructor finishes fixing fields — default values respect layout but does not prove safe publication of `this` escape (A notes it explicitly).
- Close does not await tasks, no GC/reuse, reopen undefined.
- Watch cross-branch interaction: B's `rayon_b_api.rs` expects `future_complete` API not present on C; this branch deliberately does **not** merge B's cargo changes to avoid `cargo test` breakage observed in `c-06b` attempt.

## Next

- Full `run-regressions.sh` integral still pending (deferred to C-08 final milestone to avoid tmpfs OOM on this host).
- A-03 completion requires B contract (Throwable decision) and integrated Java entry — not claimed here.
- When A pushes A-04+ or merges TODO/ROADMAP, rebase this branch on new `trabajo/a-01-contrato-heap`.

## Files in this commit

- `mc-aot/src/numeric_runtime.inc` (+34)
- `mc-aot/src/numeric_concurrent_graph_bridge.inc` (+39)
- `mc-aot/tools/numeric_bridge_layout.py` (new)
- `mc-aot/tests/check-numeric-bridge-layout.py` (new)
- `mc-aot/tests/check-numeric-auto-publish.py` (new)
- `mc-aot/run-regressions.sh` (+2)
- `analysis/c08b-integration-a03.md` (this file)
