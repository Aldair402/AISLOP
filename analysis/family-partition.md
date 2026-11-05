# C-04: Family partition — non-overlapping batches for 7762 classes

**Status:** design only, no class counted (`count_complete=0`). No percentage distributed.

## Goal

Split the inner JAR (7762 classes, SHA256 `a362163e...ee8ae6`) into 6 non-overlapping batches that follow the ROADMAP §5 order and the static closure from `analysis/dependency-summary.json` (7253 classes reachable from `Main` statically, plus 643 bundled libs). Static reachability is not execution proof — included but not sufficient.

## Batches (see `analysis/family-partition.json`)

1. **batch-01-primitives-coords** (267 classes) — `net.minecraft.core`, `com.mojang.math`. Base for all families; QuartPos lives here with partial evidence 5/6. Available.
2. **batch-02-collections-serialization** (350) — `net.minecraft.nbt` + codecs. Blocks registries/world. Available.
3. **batch-03-registries-resources** (420) — `core.registries`, `resources`, `tags`. Direct dependency of `Bootstrap.bootStrap()` → `MappedRegistry` → current `Util.makeExecutor/ForkJoinPool` blocker. **Blocked** until B-06/front-A bridge.
4. **batch-04-chunks-world** (4187) — `world.level`, `world.chunk`. Largest family; includes `ChunkStatusTasks.passThrough` stub test (80 cases). Available but depends on 01-03.
5. **batch-05-network-protocol** (630) — `network`, `protocol`. No ports opened by default per C-07 policy. Available.
6. **batch-06-entities-server** (2008) — `world.entity`, `server`, `commands`, `advancements`. Final server cycle (D-04). Available after 04-05.

Uncovered non-runtime packages (`data`, `gametest`, `sounds`, etc.) listed separately — not prioritized for server but counted in total to avoid overlap miscount.

Sum of estimates: 267+350+420+4187+630+2008 = 7862 - overlapping `net.minecraft.world` counted once — actual validator will check exact package membership via JAR listing, not estimates. Estimates are from `zipfile` package counters; validator must ensure union = 7762 and zero overlap.

## How to reserve

1. Open an issue with `ID: batch-0X`, responsable + revisor, scope, files (`TODO.md` template).
2. Claim `responsible` in `family-partition.json` via PR — one person per batch at a time.
3. Work on a dedicated branch `trabajo/c-04-...` or `trabajo/batch-0X-...` from updated `main`.
4. Do not push generated JARs, examples, or large logs; keep `downloads/` gitignored.

## Evidence vs. progress

- Existing evidence (`audit-*.json`, `quartpos-evidence-report.json`, `check-real-chunk-passthrough...`) stays in `partial-evidence` state — does not move a batch to done.
- A batch is not done until at least one class in it reaches `complete` per `class-registry.json` criteria and `count_complete` increments. No batch-level percentage inference.

## Verification

```sh
python3 mc-aot/tools/check-family-partition.py   # checks no overlap, sum=7762, blocked reasons preserved
python3 mc-aot/tools/check-class-registry.py       # counter stays 0
cargo test --manifest-path mc-aot/Cargo.toml
```

No execution of world/network code is required for this design step — static lists only. Future C-05 harness will enforce reproducible Java/native comparisons.

