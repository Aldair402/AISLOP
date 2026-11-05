# C-02: Verifiable class registry and counter

**Status:** `count_complete = 0` — no class yet satisfies ROADMAP.md §5 criteria. QuartPos remains `partial-evidence` (5/6 methods, private constructor missing), not counted.

## Purpose

Provide a single source of truth that distinguishes four states without inflating the counter from compiled methods or inventories:

- `inventoried` — class listed by hash/surface, no evidence run.
- `partial-evidence` — some members have differential tests (e.g., `analysis/class-evidence/quartpos.json` → `analysis/quartpos-evidence-report.json`), but gaps remain and `certified=false`.
- `pending-review` — evidence package assembled, awaiting reviewer and rerun verification.
- `complete` — meets all 5 ROADMAP criteria (surface reconciled including private/synthetic/`<clinit>`/flags/inheritance, translation without pending guards/stubs on admitted paths, differential evidence with edge/null/alias/concurrency where observable, explicit hashes/assumptions/limits, and rerunnable review). Only this state increments `count_complete`.

## Schema

`analysis/class-registry.json` (`schema=class-registry-v1`):

- `jar_sha256`, `jar_classes_total=7762`, `jar_url` — pin the official inner JAR `a362...ee8ae6`.
- `count_complete` — must equal `len(complete)` and be 0 until a reviewed class lands.
- `classes[]` — every tracked class with `class`, `status`, `jar_sha256`, `class_sha256`, `surface` (declared/with/without), `evidence` (manifest/report/tests/logs with sha256), `limitations`, `certified`, `review`/`reviewer`.
- `pending_review[]`, `complete[]` — kept empty while counter is 0; populated only after review.

## Verification

```sh
python3 mc-aot/tools/check-class-registry.py
```

Checks:

1. JAR hash present and matches declared inner hash; class hash verified against JAR content (via `zipfile` SHA-256).
2. Surface declared vs. manifest vs. registry consistency (no invented members, no duplicate).
3. Evidence files exist under repo root, are tracked, and SHA-256 matches registry.
4. Status logic: `partial-evidence` must have `certified=false` and non-empty `limitations`; `complete` requires `certified=true`, `review` non-null, and surface with zero `without_evidence`.
5. Counter `count_complete` equals number of `complete` entries with `status=complete` — never counts `partial-evidence` or `inventoried`. Fails if counter is non-zero without a review.

See `mc-aot/tools/check-class-registry.py` for exact rules.

## Current inventory

- `net/minecraft/core/QuartPos` — `partial-evidence`, 5/6 methods (private `<init>()V` missing), 4/4 fields. Evidence via `class-surface-evidence.py` (515 inputs/method + 4 reads). Not a complete class; does not count.

## How to propose a complete class (future C-03)

1. Add manifest `analysis/class-evidence/<name>.json` with `schema=partial-surface-v1` and run `class-surface-evidence.py --jar downloads/server-26.3-inner.jar <manifest>` to produce a report.
2. Assemble evidence logs rerun on clean clone (Java 25, Rust pinned, hashes recorded), document gaps, and open a PR with reviewer.
3. Update `class-registry.json`: move entry to `status=pending-review` then to `complete` only after reviewer rerun and explicit sign-off. Update `count_complete` manually — validator will enforce equality.

No automatic counting from `audit*.json` or method compilations. A sample does not prove universal equivalence; a hash identifies a file, not its truth.

