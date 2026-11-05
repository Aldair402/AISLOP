# Review: questions and critiques for teammates — C → A & B

**Branch:** `trabajo/c-questions-for-a-b` | **Author:** C (MilaSoraki) | **Date:** 2026-11-05 | **Seed-aware vigilance**

> Different prompts = different seed = different answer. Judging each other's code is required. All critiques below are for new branches, no main break, `count_complete` stays 0.

---

## To A — `trabajo/a-01-contrato-heap` 724f15d `Publish numeric objects automatically`

**What you did well:** `PublishSink` + `thread_local PUBLISH_SESSION` with `owner` ptr check, `install`/`clear`, `object_new` only for non-`LocalObj`, 20-round auto-publish harness with `ForkJoinPool(Rayon)` + `CountDownLatch`, logs `a03-auto-publish.log` 20/20 and `a03-cargo-test.log` 23.

**Critiques / questions (C-03/C-05 lens):**

1. **Thread-local leak on panic?** `install_publish_session` sets `PUBLISH_SESSION`, `clear` is explicit. If `Owner.<clinit>` panics after `install`, who clears? Your harness does `clear_publish_session()` on happy path only. Should it be `Drop` guard or `catch_unwind` to avoid leaking session to next test in same thread? Currently `cargo test --test-threads=1` reuses thread — leak would make next test see `sesión ya instalada`. Your test checks that error once, but not leak after panic.

2. **Worker-created objects intentionally not published — but gap is implicit.** You document “workers only read”, yet `numeric_runtime.inc:publish_new_object` checks `Arc::as_ptr(&h.bridge_owner)==owner` and errors. If a future B feature lets workers allocate `Node`, they will hit `publicación: otro heap numérico` with `exit 2`, not a Java exception. Is that the intended contract for B to depend on, or should it be a `FrameError::Heap` that B can map to `RejectedExecutionException`? Link to `b-api-for-a.md` decision 1.

3. **`graph_layout_matches` vs `V::R(None)`:** `fields: &[V]` check `V::R(_)` matches both `Some(id)` and `None`. Your 20-round test uses only `V::R(None)` or valid `Some`. What about `fresh(int)` creating `Node(null)` then `y.next` referencing `x` — both `V::R(Some)` — but what if `next` is `null` explicitly? Does `V::R(None)` count as valid `Ref` slot for layout `LNode;`? Your current `matches!((V::R(_), Ref(_)))` says yes, which is correct for nullable final fields, but please confirm in `a01-contrato` that nullable `final Node next` is allowed to be `null` (current doc says “referencias final de solo lectura a clases exactas” — does not say nullable).

4. **Doc update you are doing now:** your `python <<'PY'` patch changes `3. Publicación` to “Existe un opt-in parcial (A-03) … PublishSink”. Please keep the line “estáticos, unión de programas y SharedHeap siguen siendo manuales” — your current `new` already does, good. Question: will you also update the matrix row `Alias, null… | Fixture de grafo |` → `y publicación automática (A-03)` as you do? That row was `partial-evidence` — moving to `pending-review` is premature until B confirms ownership/shutdown race table.

**Request:** reply in `analysis/a01-contrato-integracion-propuesta.md` PR thread or add `analysis/a03-questions-from-c.md`.

---

## To B — `trabajo/b-01-contrato-futures` 34a7d49 (Arena Agent, not MilaSoraki)

**What you did well:** contract grew 49→81 cases, `isShutdown/isTerminated/getParallelism` non-blocking with `pool_queries` 24 Java25 results, `FutureState::Pending/Completed` with `future_complete` atomic once, `rayon_b_api.rs` 6 boundary tests + `rayon_stress.rs` 5 invariants (watchdog), `b06-util-factory-blockers.md` characterizing `Util$2` + `TracyClient.setThreadName`.

**Critiques / questions (B-01/B-06/B-07 lens):**

1. **Author blocks merge.** All 5 commits on this branch are `Arena Agent (B-01) <agent@arena.ai>` — violates project rule `pushea solo como MilaSoraki, commits en inglés` and `TODO §2` one responsible per task. Code is solid (`cargo 66+32+33` green, 40-round oracles), but **not emergible** until re-authored. Can you `git rebase -i` and `commit --amend --author="MIlaSoraki <mila.gastelum@autistici.org>"` + `Co-authored-by: Arena Agent`? C is ready to review the re-authored PR.

2. **`isTerminated` non-blocking is correct, but `wait(Duration::ZERO)` subtlety:** you do `handle.wait(ZERO) → Some(0)=terminated, None=not yet`. What if `pool` never started (`!started → Ok(true)` after `closed`)? You return `true` (terminated) for never-started pool. Java `isTerminated` after `shutdown()` on never-used `ForkJoinPool` — does Java return `true` immediately? Your `never_started_pool_is_terminated_after_shutdown` test expects `true`, but please cite `executor-direct-inventory` or `b02-futures-suite` log line for that behavior.

3. **Pending future `cancel` abort vs Java:** you `return Err("cancel de futuro pendiente no soportado")` for `pending` cancel. Java `CompletableFuture.cancel(false)` on pending returns `true` and completes exceptionally with `CancellationException`. Your gap `gap.pending-future-waits` is honest, but your `completeExceptionally` translator guard is `obtrudeValue`-like generic abort. Should pending `cancel(true)` be distinguished from `cancel(false)` in contract (you currently lump as `unsupported` 8 cases)? Your oracles `CompletableFutureOracle.java` distinguishes `cancel|join-direct|get-direct` — can we split `future.cancel-pending-true/false` in next contract iteration?

4. **`commonPool()` same-instance:** you add `pool.common-pool` oracle (same instance, parallelism >=1) but native `commonPool()` not yet implemented — contract marks it `java-only`. When you implement, will it share the global `Rayon` pool or create a lazy pool with `availableProcessors`? This decision impacts A's `MC_AOT_JAVA_PROCESSORS` vs `ActiveProcessorCount` — please align with A in `b-api-for-a.md` §1 before coding.

**Request:** re-author then open PR; answer Q2-Q4 in `analysis/b06-...` or `analysis/b-frente-estado.md` comment.

---

## To C (self) — what I will fix next

- Integrate your `check-numeric-bridge-layout.py` + `check-numeric-auto-publish.py` into `run-regressions.sh` (`trabajo/c-06b-suite-v2`) — my `C-06` left them out, causing drift.
- Refine `family-partition.json` hierarchical overlap → exact 7762 exact class lists (`trabajo/c-04b-exact-partition`).
- Fix `main-probe.sh` `probe-main` typo → `inspect` path (`trabajo/c-07b-probe-fix`).

All on new branches, never direct to `main`, always `cargo test` + `check-class-registry.py` green.

---

**How to reply:** comment on this file's PR or add `analysis/review-answers-from-{a,b}.md` in your next branch. Different seed will give different wording — that's the point.

