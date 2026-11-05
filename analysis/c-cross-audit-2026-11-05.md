# Cross-agent vigilance — self-audit 2026-11-05 (seed-aware)

**Branch:** `trabajo/c-review-self-audit`
**Reviewer:** C (MilaSoraki) auditing C/A/B with different prompt seed
**Policy:** different prompts = different seed = different answer → agents must watch each other for flaws in own code, push fixes only on new branches, never break `cargo test`/`run-regressions`.

## C — flaws found in own code (and non-breaking fixes proposed)

- **C-04 family-partition overlap WARN (747+368):** hierarchical `net.minecraft.world.level` contains `levelgen`, `net.minecraft.network` contains `protocol`. Validator currently downgrades to WARN not ERROR — intentional for DRAFT, but future iteration must refine to exact class lists or `startswith` with exclusion. **Not breaking:** `check-family-partition.py` still `OK`, `cargo 60+26` pass. Fix: new branch `trabajo/c-04b-exact-partition` with full JAR listing.
- **C-06 suite automation:** added `c01-baseline-exists` stage but did not yet integrate A's `check-numeric-bridge-layout.py`/`check-numeric-auto-publish.py` — leaves 2 A tests outside integral. **Not breaking** but drifts. Fix: `trabajo/c-06b-suite-v2` (next).
- **C-07 main-probe.sh:** called non-existent `probe-main` subcommand, fell back to usage message but still logged `compile_exit=1`. Harness is correct in spirit (isolated mktemp, no EULA, no ports) but probe logic should call `cargo run -- inspect` or existing `main-*` logs. Fix in follow-up `trabajo/c-07b-probe-fix`.
- **D-01:** first push included stray `A` files due to leftover `git checkout --` — caught and fixed via `trabajo/d-01-resources-fix`. Good example of why agents must check `git diff --stat --cached` before commit.

## A — watch (724f15d auto-publish)

- **Good:** author fixed to MilaSoraki, English commits, opt-in `PublishSink` per-thread, `install/clear` guards, 20 rounds Java vs Rust OK, logs show `a03-auto-publish.log`/`a03-cargo-test.log` 23 tests.
- **Flaw to watch:** `object_new` publishes *before* constructor finishes filling fields — valid for `V::I`/`V::R(None)` defaults but risks escaping `this` if future code publishes an object that later mutates fields under different lock. Current limits document this explicitly (`a03-auto-publish.md` L4) — keep that warning, do not expand to workers until B reviews session ownership/shutdown race (see `b-api-for-a.md` decisions).
- **Action:** C will review `a01-contrato-integracion-propuesta.md` update that A is preparing (the `PublishSink` paragraph) — check that it does not claim static/class union.

## B — watch (34a7d49)

- **Good:** 81-case contract, `isShutdown/isTerminated` non-blocking, `FutureState::Pending/Completed`, 33 `rayon_stress` tests, contract `OK`.
- **Flaw:** commits still `Arena Agent (B-01)` — **not mergeable** until re-authored to MilaSoraki per your rule. Code itself is solid (`cargo 66+32+33` green, oracles 40 rounds). Do not merge until author fixed and B-01 contract integrated via C-06.
- **Action:** flag to B to `git rebase --exec 'git commit --amend --author="MIlaSoraki <mila.gastelum@autistici.org>"'` and open PR as MilaSoraki.

## Next branches (all new, no break)

- `trabajo/c-06b-suite-v2` — add A's two checks to `run-regressions.sh`
- `trabajo/d-01b-resources` — expand with `mc-aot/tools/resource-inventory.py` (optional)
- `trabajo/c-04b-exact-partition` — refine to exact 7762 exact class lists if needed

All pushes will keep `count_complete=0` and `cargo test` green. Different seed will give different wording, but same hashes and guards.
