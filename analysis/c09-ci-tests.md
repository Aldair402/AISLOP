# C-09: CI for quick validation while A/B run full regressions

**Branch:** `trabajo/c-09-ci-tests` · **Base:** `main` 37f0041 (A-03 + C-08b + B merged)
**Date:** 2026-11-05 · **No code change to runtime — only `.github/workflows/ci.yml`**

## Why CI now

A and B still run `mc-aot/run-regressions.sh` locally (A's `full-regressions-a03.log` 306 etapas, B's `full-regressions-b-frente-contrato-futures-retry2.log` pending `sleep 1200` watch). B found `No space left on device (os error 28)` when `TMPDIR=/tmp` (992 MB tmpfs) filled with `cargo target` (274 MB + 619 MB). CI must not repeat that.

## Jobs (as sketched in C-06, now implemented)

- `quick` (push/PR, <2 min, no JAR): `cargo test --manifest-path mc-aot/Cargo.toml` (60+26+33) + `check-class-registry.py` + `check-family-partition.py`. Fails fast, no disk pressure. Runs on every `trabajo/*` and `main` push.

- `focused` (needs JAR, ~10 min, after quick): runs only if `downloads/server-26.3-inner.jar` present (repo `.gitignore`s `downloads/`). Executes `QuartPos` + `numeric-bridge-layout` + `numeric-auto-publish` + `futures-contract` + `rayon-pending-future`. Uses `CARGO_TARGET_DIR=${{ github.workspace }}/target` and `TMPDIR=${{ runner.temp }}` (fixes B's tmpfs bug). Skips gracefully with `::warning::` if JAR missing in CI (expected — JAR not committed).

- `full` (manual only `workflow_dispatch`, 45 min timeout): runs `bash mc-aot/run-regressions.sh` with same `TMPDIR`/`CARGO_TARGET_DIR` fix, `df -h` before/after, `echo EXIT=$?` and `grep -c '^==> '` etapas check (B's watch command), uploads `analysis/full-regressions-*.log` as artifact (7 days, no JAR upload). Partial/interrupted run cannot be presented as `Todas las regresiones terminaron correctamente` — checks exit code and tail.

No `306 etapas, exit 0` claimed here — CI only validates; approved integral remains `full-regressions-a03.log` until a human pushes a new verified log.

## Local verification

```
cargo test --manifest-path mc-aot/Cargo.toml              # 60+26+33 OK
python3 mc-aot/tools/check-class-registry.py              # 0.1s
python3 mc-aot/tools/check-family-partition.py            # 0.1s
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" # YAML OK
```

No `main` push yet — branch ready for review.

