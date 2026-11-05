# C-03: Complete-class candidate — QuartPos (not certified)

**Class:** `net/minecraft/core/QuartPos`
**Branch:** `trabajo/c-03-first-complete-class`
**Date:** 2026-11-05
**Reviewer:** C (MilaSoraki) — self-review for gap analysis, not certification
**Status:** `partial-evidence` — does NOT meet ROADMAP §5 criteria; `count_complete` stays 0.
**Related registry:** `analysis/class-registry.json` (QuartPos: partial-evidence), `analysis/quartpos-evidence-report.json`

## 1. Declared surface reconciled with classfile

**JAR:** `downloads/server-26.3-inner.jar` SHA256 `a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6` (official 26.3 inner, 7762 classes)
**Class:** `net/minecraft/core/QuartPos` SHA256 `0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c`
**Superclass:** `java/lang/Object` — final class, no superclass beyond Object
**Interfaces:** none
**Flags:** `0x0031` = `public final super` (final, no synthetic)
**Version:** 69 (Java 25 bytecode)

**Fields (4):**
- `public static final int BITS` (0x0019)
- `public static final int SIZE` (0x0019)
- `public static final int MASK` (0x0019)
- `private static final int SECTION_TO_QUARTS_BITS` (0x001a)

**Methods (6):**
- `private <init>()V` — code=5, handlers=0, instr=3, arg slots 0 — `aload_0; invokespecial Object.<init>; return`
- `public static fromBlock(I)I` — ishr 2
- `public static quartLocal(I)I` — iand 3
- `public static toBlock(I)I` — ishl 2
- `public static fromSection(I)I` — ishl 2
- `public static toSection(I)I` — ishr 2

Verified via:
```sh
cargo run --manifest-path mc-aot/Cargo.toml -- inspect downloads/server-26.3-inner.jar net/minecraft/core/QuartPos
javap -p -c -cp downloads/server-26.3-inner.jar net.minecraft.core.QuartPos
```
Outputs stored in `analysis/quartpos-static-surface.log` (hash `af6a0d5b1ebf5707187d77924336a0e3d746087971a56497486dad18121ea230`).

No `<clinit>` — static finals are compile-time constants (int literals), no initializer to model.

Inheritance/behavior: final class extends Object, no overridden methods beyond Object defaults (toString/equals not declared). Consumers examined: none beyond static calls; QuartPos is used as pure functions, no instance state.

## 2. Translation and dependencies

Current backend: `multi-static-demo` in `mc-aot` can translate the 5 public static methods as numeric primitives (no objects, no exceptions) with exact Java semantics for `int` arithmetic (shift/mask) over full `int32` domain. Limits: none for these methods; heap not involved.

Private constructor: **not translated**. `mc-aot` rejects `new QuartPos` because instantiation of this final utility class is not a supported object allocation (no fields of instance, no GC). Reflection `QuartPos.class.getDeclaredConstructor().newInstance()` not modeled — would require private access, instantiation guard.

All other ops are pure int math — no initialization, identity, types, dispatch, exceptions, state changes beyond return value. No dependencies beyond `java/lang/Object.<init>`.

## 3. Differential evidence — fresh run on this host (2026-11-05, JDK 25.0.5, Rust 1.99.1)

**Test:** `mc-aot/tests/check-quartpos-class-surface.py`

- 515 random int inputs per method + 4 field reads = 2579 + 4 = 2583 comparisons Java vs native
- Field identity: `BITS`, `SIZE`, `MASK`, `SECTION_TO_QUARTS_BITS` read via reflection, compared
- Result: `OK: 2579 resultados, cinco métodos y cuatro campos declarados de QuartPos oficial; no prueba constructor privado...`

Evidence files:
- `mc-aot/tests/check-quartpos-class-surface.py` SHA256 `f929121207670f2eeed744b1bb4cbc2b02abd69a820e55865dbe4850b87f25cb`
- `analysis/quartpos-static-surface.log` SHA256 `af6a0d5b1ebf5707187d77924336a0e3d746087971a56497486dad18121ea230`

**Full-surface manifest:** `analysis/class-evidence/quartpos.json` (schema partial-surface-v1) covers 5/6 methods, 4/4 fields. Verified with:
```sh
python3 mc-aot/tools/class-surface-evidence.py analysis/class-evidence/quartpos.json
# → 5 methods_with_partial_evidence, 4 fields_with_partial_evidence, certified=false
python3 mc-aot/tools/check-class-registry.py
# → OK: 1 tracked, count_complete=0
```

## 4. Explicit gaps — why NOT complete (per ROADMAP 5 criteria)

1. **Surface not fully covered:** private `<init>()V` absent from evidence. No differential for:
   - direct `new QuartPos()` or reflective instantiation (private access, exception on second instantiation attempt)
   - class initialization side-effects (none, but must be proven, not assumed)
   - inherited Object methods (equals/hashCode) observed via callers — not in current test suite

2. **Translation incomplete:** numeric backend does not emit constructor; a native caller that tried to instantiate would abort, not reproduce Java's `IllegalAccessException`/`InstantiationException`. No heap, identity, monitor, GC path exercised.

3. **Evidence limited to samples:** 515 random values per method covers corners (-2^31, -1, 0, etc.) but is not a proof over 2^32 domain; no property test, no mutation of static finals via reflection (which Java allows with setAccessible, we reject).

4. **No concurrency/resource/IO/reflection beyond static reads:** not relevant for this pure class, but must be stated.

5. **No rerunnable review package for complete:** to certify, would need a second independent rerun, reviewer sign-off, and PR linking all hashes/logs. Not present.

Therefore `certified=false`, `status=partial-evidence`, `count_complete=0` stays.

## 5. Repro steps

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH="$HOME/.cargo/bin:$JAVA_HOME/bin:$PATH"
cargo run --manifest-path mc-aot/Cargo.toml -- inspect downloads/server-26.3-inner.jar net/minecraft/core/QuartPos
python3 mc-aot/tests/check-quartpos-class-surface.py
python3 mc-aot/tools/class-surface-evidence.py analysis/class-evidence/quartpos.json
python3 mc-aot/tools/check-class-registry.py
cargo test --manifest-path mc-aot/Cargo.toml  # 60+26
```

## 6. Decision

**Do not increment counter.** Keep `analysis/class-registry.json:count_complete=0`. If constructor and full inheritance proof are added with differential and review, promote to `pending-review` then `complete` via PR — not by editing this report alone.

Alternatives considered: `BelowZeroRetrogen$1`, `LevelHeightAccessor$1` have object state and require heap/monitor — larger gaps, not smaller. QuartPos remains the smallest viable candidate precisely because its gaps are explicit (one private constructor).

