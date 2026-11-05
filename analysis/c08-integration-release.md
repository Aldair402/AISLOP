# C-08: Integration and release of batches

**Branch:** `trabajo/c-08-integration-release`
**Counter:** `count_complete=0` — unchanged; no batch claims completion.
**Base:** `8fa1893` + C-01..C-07 pushed as separate PRs.

## Scope

C-08 reviews PRs from A/B, resolves interface conflicts with both responsables, runs changed focal tests then full integral before declaring a milestone. It does not count a batch by methods compiled.

## PRs ready for review (pushed as MilaSoraki, English commits)

- `trabajo/c-01-baseline` — `be5be6d` C-01: add collaborator baseline (Debian trixie, Rust 1.99.1, JDK 25.0.5, SHA1/SHA256 verified, cargo 60+26, first blocker ForkJoinPool)
- `trabajo/c-02-verifiable-inventory` — `10c9a87` C-02: verifiable registry `class-registry-v1` with QuartPos partial-evidence 5/6, counter 0
- `trabajo/c-03-first-complete-class` — `397340e` C-03: QuartPos candidate reconciled (6 methods incl. private <init>, 4 fields) — gaps explicit, not certified
- `trabajo/c-04-family-partition` — `92f9cd6` C-04: 6 non-overlapping batches (5801 covered + 9 uncovered groups = 7762), batch-03 blocked on Util.makeExecutor
- `trabajo/c-05-differential-harness` — `482a4ff` C-05: harness contract (seed 263, PATH-stripped native, stub labeling)
- `trabajo/c-06-suite-automation` — `94b111a` C-06: registry+partition checks added to `run-regressions.sh` (3 stages), CI sketch, B-01 pending merge
- `trabajo/c-07-isolated-boot-probe` — `6eab0df` C-07: `main-probe.sh` in mktemp, no EULA, no ports, blocker reproduced

All branches derived from updated `main` (8fa1893), no direct pushes to `main`, each task isolated per TODO §2.

## Conflicts and interface decisions

- `mc-aot/run-regressions.sh` touched by C-06 and B-01 (B-01 adds ~80 new checks on its branch). Resolution: keep C-06's 3 new stages; B-01's `check-futures-contract` will be added after B-07 merges to avoid false red (see C-06 doc).
- `TODO.md` lives only on `trabajo/b-01-contrato-futures` — not on `main` yet; C-08 will propose adding it via PR once C-02 registry is approved, to avoid divergent TODO.
- `mc-aot/src/*` not modified in C — no conflict with A/B runtime changes. C's tools are additive under `analysis/` and `mc-aot/tools/`.

## Verification performed (focal)

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH="$HOME/.cargo/bin:$JAVA_HOME/bin:$PATH"
cargo test --manifest-path mc-aot/Cargo.toml              # 60+26 OK
python3 mc-aot/tools/check-class-registry.py              # OK 1 tracked 0 complete
python3 mc-aot/tools/check-family-partition.py            # OK 6 batches 5801 unique
python3 mc-aot/tests/check-quartpos-class-surface.py      # OK 2579
python3 mc-aot/tests/check-numeric-completed-future.py    # OK 90
python3 mc-aot/tests/check-real-chunk-passthrough-future.py # OK 80
bash mc-aot/tools/main-probe.sh                           # compile_exit=1 blocker
```

## Full integral

Last approved integral remains `analysis/full-regressions-completed-future.log` (306 stages, exit 0). No new full integral claimed in these PRs — each PR ran focal validators; full re-run is scheduled after A-07/B-07 interface lands. When run, use:

```sh
bash mc-aot/run-regressions.sh > analysis/full-regressions-c08-$(date +%Y%m%d).log 2>&1; echo $?
```

Check `echo $?` and log tail — do not present interrupted run as approved.

## Release notes for roadmap

- **Before:** 0 complete, blocked at `new ForkJoinPool` via `Util.makeExecutor`
- **After C PRs:** 0 complete (no regression), but reproducible baseline, verifiable counter, candidate review template, family assignment, harness contract, suite automation, and isolated probe are now versioned. Next unblock depends on B-06/B-07 factory/handler and A-07 connector — tracked in `b06-util-factory-blockers.md` and `b-api-for-a.md` on `trabajo/b-01-contrato-futures`.

No JARs, binaries, or private keys were committed; `downloads/` stays gitignored; all pushes authenticated as `MilaSoraki <mila.gastelum@autistici.org>` via deploy key `SHA256:M0LjD...Ek` (ED25519) with write access scoped to AISLOP.

