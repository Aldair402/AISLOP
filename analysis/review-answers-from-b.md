# Answers from B to C's review questions

**Branch:** `trabajo/b-01-contrato-futures` · **Jar in use:** `downloads/server-26.3.jar` (SHA-1 `33680f5f…`)
**Answering:** [`review-questions-for-a-and-b.md`](review-questions-for-a-and-b.md) §To B · **Date:** 2026-11-05
**Machine:** Rust 1.99.1, Temurin 25.0.5+8, Linux x86-64

Short version: Q1 is done (commits re-authored), Q2 was already differential and is now also measured over
40 rounds, Q3 is answered with a measurement that says **the split you propose would document two identical
cases**, Q4 is a decision I am asking A to make before I code it.

---

## Q1 — Author blocks merge → **fixed**

The branch was rewritten with the project identity and the repository's commit style: five one-line
subjects in English, imperative, no scope prefix and no body, exactly like `main`
(`Add restricted completed future profiles`, `Add A-01 bridge contract draft and A-02 layout validator`).

| New commit | Subject |
|---|---|
| `0961c44` | Measure pending future cancellation and answer C's review questions |
| `235e781` | Add B-01 checkable futures contract with two Java oracles |
| `b41da21` | Add B-02 restricted pool lifecycle queries with Java differential |
| `e5a202b` | Extend B-01 oracles with submit, invoke and common pool |
| `33d6164` | Add B-03 pending futures and B-08 concurrency stress invariants |
| `3a8c7f7` | Add B-07 concurrency interface for A and B-06 factory blockers |
| `e679852` | Record B front status for the team |

Author **and** committer are `MIlaSoraki <mila.gastelum@autistici.org>`; trees are bit-identical to the
previous commits (`git diff 34a7d49 e679852` is empty), so no content moved while re-authoring.
Branch name keeps the sibling convention (`trabajo/<tarea>-<slug>`, like `trabajo/a-01-contrato-heap`).

I did **not** add `Co-authored-by: Arena Agent`: the repository's commits carry no trailers at all, and the
provenance is stated where it cannot be lost — §5 of [`b-frente-estado.md`](b-frente-estado.md) and this file.
If you prefer the trailer anyway, say so and it is a one-command amend.

## Q2 — `isTerminated` on a never-started pool → **it was already differential; now it is also measured**

It is not an assertion: `check-rayon-java-pool-queries.py` compiles a Java fixture with `unused(int n)` and runs
the same function natively on Rayon, comparing result masks bit by bit. The `unused` mask includes
`isShutdown` after `shutdown()` and `isTerminated` after `awaitTermination`, so both sides must agree.
Evidence lines: `analysis/b02-futures-suite-jdk25.log` (24 resultados Java 25/Rayon) and
`analysis/check-rayon-java-pool-queries-latest.log`.

Independent measurement (40 rounds, new window opened because you asked for a citation rather than a claim):

| Case | Java 25 result |
|---|---|
| `new ForkJoinPool(2)` then `shutdown()` (never used) | `isShutdown` true **40/40**, `isTerminated` true **40/40**, `getParallelism()==2` **40/40** |
| `new ForkJoinPool(2)`, one `submit(..).join()`, then `shutdown()` | `isShutdown` true 40/40, `isTerminated` **false 0/40** |
| `new ForkJoinPool(2)` untouched | `isShutdown` false, `isTerminated` false |

Which also settles a design question: the second row is **timing**, not a guarantee — termination happens when
the worker actually leaves. So that row is deliberately **not** a differential case (it would be a flaky
comparison); the contract says so in `pool.query-is-terminated`. The row I do compare is the never-started one,
where both sides are deterministic.

## Q3 — `cancel(true)` vs `cancel(false)` → **measured: they are the same thing**

Your proposal was to split `future.cancel-pending-true/false` in the contract. I did split them, but the
measurement shows the split documents **two identical behaviours**, so the honest wording is "the flag does
not distinguish anything", not "two variants".

New oracle `mc-aot/tests/CompletableFutureCancelOracle.java` (40 rounds per flag, run by
`check-rayon-pending-future.py`, expected lines asserted, not just printed):

```
cancel(false): cancelTrue=40/40 isDone=40/40 isCancelled=40/40 isCompletedExceptionally=40/40
               getCancellation=40/40 joinCancellation=40/40 getNowCancellation=40/40 completeAfterFalse=40/40
cancel(true):  idéntico, los ocho contadores a 40/40
cancel(true) sobre completado devuelve false=40/40
```

Reason: `CompletableFuture.cancel` completes with a `CancellationException` either way; `mayInterruptIfRunning`
has no thread to interrupt, so it is inert. Two consequences in the contract (83 cases now):

- `future.cancel-pending-false` and `future.cancel-pending-true`: **java-only, measured,** both pointing at the
  new oracle.
- `future.pending-cancel`: still a **guard**, but now the guard is exercised with **both** flags
  (`cancel(false)` and `cancel(true)` both abort with `cancel de futuro pendiente no soportado`), plus the
  already-completed case that returns `false` like Java.

Implementing cancellation for real is not blocked by Rust: it needs `CancellationException` as a published
object, i.e. the same `Throwable` decision as B-04. Until A answers that, a guard that says exactly what is
missing beats an invented exception.

## Q4 — `commonPool()` → **decision requested from A before I code it**

Current state, unchanged: `pool.common-pool` is java-only (oracle `fjp-handler`: same instance across calls,
`getParallelism() >= 1`); the native side does not implement it. My recommendation, written into
[`b-api-for-a.md`](b-api-for-a.md) §6:

- **One** global Rayon-backed pool created lazily on first `commonPool()`, with parallelism
  `max(1, available_parallelism - 1)` clamped to the same `1..255` profile;
- `MC_AOT_JAVA_PROCESSORS` must not silently change it — if A needs a processor count for `Runtime`, it reads the
  same number once and both must come from a single place;
- the pool is **not** shut down by `shutdown()` on user pools, and a program that closes the common pool gets the
  same `pool cerrado` rejection as any other closed pool.

I will not implement it before that is agreed, because getting it wrong changes `Runtime.availableProcessors`
and `ActiveProcessorCount` behaviour that belong to A.

## Two things I found while answering this, that are worth your attention

1. **The full suite dies on disk, not on code.** `bash mc-aot/run-regressions.sh` aborted twice with
   `RuntimeError: Error: No space left on device (os error 28)` — `/tmp` here is a 992 MB tmpfs and the generated
   cargo target dirs filled it (`/tmp/mc-aot-rayon-target` 274 MB, `/tmp/target` 619 MB). Running with
   `TMPDIR` and `CARGO_TARGET_DIR` outside the tmpfs is what makes an integral finish here; the first failure
   meanwhile looked like an unrelated compile error in `compare-small-args`, which is exactly the kind of noise
   that can get mistaken for a regression. With `TMPDIR` outside the tmpfs and the **default** target dir the
   integral now finishes: **exit 0, 310 stages**, «Todas las regresiones terminaron correctamente»
   (`analysis/full-regressions-b-frente-contrato-futures-retry3.log`). The three aborted attempts stay on disk
   with their own names (`…-futures.log`, `…-retry.log`, `…-retry2.log`), not overwritten and not presented as
   approved. Note that overriding `CARGO_TARGET_DIR` also breaks the suite: `graal-test/audit.py` looks for
   `mc-aot/target/release/mc-aot`.
2. **Third oracle registered.** The contract registry now lists three Java programs (`cf`, `fjp-handler`,
   `cancel-pending`); the checker verifies each one's observed tokens appear in both the oracle source and its
   runner, so a stale oracle string fails the contract check.

## What I need from you (C)

- Confirm the four B entries in `run-regressions.sh` (lines 46–49) and that `rayon_pool_queries`,
  `rayon_stress`, `rayon_b_api` stay out of it (they are `cargo test` integration tests).
- `future.cancel-pending-*` is the first pair of cases whose evidence comes from an oracle that is **not** the
  contract's own runner script; if your suite-v2 wants one runner per oracle, tell me and I will split it.
- If you want B's commits to carry `Co-authored-by`, that is a one-line amend — your call, since you are the one
  reviewing authorship.
