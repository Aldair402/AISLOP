# C-10 — CI fixes: valid runner context and JAR-backed checks

**Branch:** `trabajo/c-10-ci-jar-fetch` · **Base:** `main` 1a0548d · **Date:** 2026-11-05

## Why CI was red

Two different failures, both on every run of `.github/workflows/ci.yml`:

1. **Invalid workflow file (runs #1–#3, sha 663dc9e/638381e/b18d867).**
   Annotations at L40 and L73: `Unrecognized named-value: 'runner'` inside
   `env: TMPDIR: ${{ runner.temp }}`. The `runner` context is not available in
   a job-level `env:` block, so GitHub rejected the whole workflow before any
   job started. Fixed by setting `TMPDIR` from a step through `$GITHUB_ENV`.

2. **`registry and partition` exit 1 (run #4, sha 1a0548d).**
   Both checks open `downloads/server-26.3-inner.jar`, which is gitignored, so a
   fresh CI checkout has no JAR and the scripts died with `FileNotFoundError`.
   `cargo test` itself was green.

## What changed

- `.github/workflows/ci.yml`
  - `quick`, `focused` and `full` now fetch the official Mojang bundle and
    extract the inner JAR before any JAR-backed check, cached by
    `actions/cache` under the pinned inner-JAR digest.
  - Job-level `env` only uses `${{ github.workspace }}` / `${{ env.* }}`;
    `TMPDIR` and `CARGO_TARGET_DIR` are exported from a step.
  - `actions/checkout@v5` and `actions/setup-java@v5` (Node 20 deprecation and
    the setup-java v4 deprecation notice).
  - baseline guard now emits a `::warning::` annotation instead of a silent echo.
  - quick timeout 10 → 15 min to cover the first, uncached JAR download.
- `mc-aot/ci/fetch-server-jar.sh` (new): verifies SHA-1 of `server-26.3.jar`,
  extracts `META-INF/versions/26.3/server-26.3.jar`, verifies SHA-256 of the
  inner JAR, and is idempotent on a cache hit. Digests match README §Descarga.
- `mc-aot/tools/check-class-registry.py` and `check-family-partition.py` now
  degrade gracefully when the JAR is absent: structural validation still runs
  (schema, totals, statuses, evidence files, duplicate packages, blocked
  reasons) and the output says "hashes unverified" / "?" counts instead of
  pretending to have measured. `count_complete` logic is untouched: the counter
  is still derived only from `complete` entries, never from the compiled JAR.

## Verification

- `bash mc-aot/ci/fetch-server-jar.sh` on a checkout without the inner JAR:
  `extracted ... 26652008 bytes` then `downloads/server-26.3-inner.jar: OK`.
- `python3 mc-aot/tools/check-class-registry.py` with JAR:
  `OK: registry valid — 1 tracked, count_complete=0 ..., 7762 classes verified against JAR`.
- Same script in a temp root without `downloads/`:
  exit 0 with `WARN: ... structural checks only, class hashes unverified`.
- `python3 mc-aot/tools/check-family-partition.py`: with JAR `5801 / 7762`;
  without JAR `? classes ... unverified`, exit 0 both ways.
- `cargo test --manifest-path mc-aot/Cargo.toml`: 60 + 26 + 33 passing.
