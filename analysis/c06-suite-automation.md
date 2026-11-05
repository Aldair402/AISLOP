# C-06: Suite and automation

**Status:** integrated, no fake approval. Counter 0.
**Branch:** `trabajo/c-06-suite-automation`

## Changes to `mc-aot/run-regressions.sh`

Added after `check-class-surface-evidence`:

```sh
run_logged check-class-registry python3 mc-aot/tools/check-class-registry.py
run_logged check-family-partition python3 mc-aot/tools/check-family-partition.py
run_logged c01-baseline-exists test -f analysis/c01-baseline-2026-11-05.md
```

These three are lightweight (<1s), verify JAR hash `a362...ee8ae6`, registry counter=0, partition unique cover 5801, and baseline presence. They run after `cargo-test` and before heavy oracles, so failure is fast.

**B-01 contract (`check-futures-contract.py`):** prepared locally but not yet in suite — requires `analysis/futures-contract-b01.json`, `TODO.md` and B-07 `rayon_b_api.rs` tests that live only on `trabajo/b-01-contrato-futures` (not yet merged to `main`). Documenting as pending avoids false green. Once B-07 merges, add:

```sh
run_logged check-futures-contract python3 mc-aot/tests/check-futures-contract.py
```

## Focal commands

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH="$HOME/.cargo/bin:$JAVA_HOME/bin:$PATH"
cargo test --manifest-path mc-aot/Cargo.toml                         # 60+26, ~10s
python3 mc-aot/tools/check-class-registry.py                         # 0.1s
python3 mc-aot/tools/check-family-partition.py                       # 0.1s
python3 mc-aot/tests/check-quartpos-class-surface.py                 # 2s, 2579 cases
python3 mc-aot/tests/check-numeric-completed-future.py               # 90 cases
```

## Full integral

```sh
bash mc-aot/run-regressions.sh > analysis/full-regressions-c06-suite.log 2>&1; echo $?
```

- **Expected:** 309 stages (306 base + 3 new) if B-01 not yet added; 310 with B-01.
- **Timing:** ~25-35 min on 1.9Gi/2-core trixie; requires JDK 25 and `downloads/` verified (see C-01). Do not run two integrals in same tree (analysis/*-latest.log race).
- **Status on this host:** not re-run fully for this PR — focal tests and validators pass (see above). Full 306-stage log from base commit remains the last approved integral; this PR does not claim a new approved integral.

## CI sketch (not yet enabled)

If CI is added, describe exactly:

- **Job 1 `quick`:** `cargo test` + two validators (no JAR download, <2 min, 1Gi limit).
- **Job 2 `focused`:** needs JAR (download + hash check), runs 5-10 `check-*` (10 min, 2Gi).
- **Job 3 `full`:** needs JAR, runs `run-regressions.sh` with 40 min timeout, 4Gi, artifact `analysis/full-regressions-*.log` only, never upload JARs. No `analysis/full-regressions-*.log` overwrite — use `${TASK}` suffix.

Partial or interrupted run must not be presented as `Todas las regresiones terminaron correctamente`. Check exit code and log tail.

