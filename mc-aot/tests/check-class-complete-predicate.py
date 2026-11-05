#!/usr/bin/env python3
"""Exercise the class-complete predicate and try to cheat it.

The predicate in `mc-aot/tools/class-complete-predicate.py` decides the counter,
so this check does two things: it asserts the verdict of the real registry, and
then it mutates a copy of the evidence seven ways to prove each rule actually
bites. A predicate nobody attacks is a comment with syntax.

Every mutation runs in a temporary tree; nothing in `analysis/` is touched.
"""
import copy, importlib.util, json, pathlib, shutil, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
PREDICATE = ROOT / "tools/class-complete-predicate.py"
REGISTRY = PROJECT / "analysis/class-registry.json"
REPORT = PROJECT / "analysis/quartpos-evidence-report.json"
CLASSFILE = PROJECT / "analysis/class-evidence/quartpos-classfile.json"


def load_predicate():
    spec = importlib.util.spec_from_file_location("class_complete_predicate", PREDICATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage(tmp):
    """Copy the three evidence inputs into a throwaway project tree."""
    root = pathlib.Path(tmp)
    (root / "analysis/class-evidence").mkdir(parents=True)
    shutil.copy(REGISTRY, root / "analysis/class-registry.json")
    shutil.copy(REPORT, root / "analysis/quartpos-evidence-report.json")
    shutil.copy(CLASSFILE, root / "analysis/class-evidence/quartpos-classfile.json")
    return root


def read(root, rel):
    return json.loads((root / rel).read_text())


def write(root, rel, data):
    (root / rel).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def verdict(module, root):
    registry, results, computed = module.evaluate(root / "analysis/class-registry.json", root)
    return registry, results[0] if results else None, computed


def main():
    module = load_predicate()

    # 0. The real registry, as committed.
    registry, result, computed = verdict(module, PROJECT)
    if result["verdict"] != "review-required":
        raise SystemExit(f"QuartPos debería estar review-required, está {result['verdict']}: {result['blockers']}")
    if set(result["blockers"]) != {"no-review", "no-reviewer", "not-certified"}:
        raise SystemExit(f"bloqueos inesperados para QuartPos: {result['blockers']}")
    if not any(n.startswith("java-only-unreachable:<init>()V") for n in result["notes"]):
        raise SystemExit("el constructor privado no aparece como java-only inalcanzable")
    if computed != 0 or registry["count_complete"] != 0:
        raise SystemExit(f"el contador debe ser 0, predicado={computed} registro={registry['count_complete']}")

    with tempfile.TemporaryDirectory(prefix="mc-class-predicate-") as tmp:
        root = stage(tmp)
        base_report = read(root, "analysis/quartpos-evidence-report.json")
        base_registry = read(root, "analysis/class-registry.json")

        def reset():
            write(root, "analysis/quartpos-evidence-report.json", copy.deepcopy(base_report))
            write(root, "analysis/class-registry.json", copy.deepcopy(base_registry))

        def expect(label, mutate, *, expect_verdict, expect_blocker=None, registry_counter_mismatch=False):
            reset()
            mutate()
            reg, res, comp = verdict(module, root)
            if expect_verdict and res["verdict"] != expect_verdict:
                raise SystemExit(f"[{label}] veredicto {res['verdict']} != {expect_verdict}: {res['blockers']}")
            if expect_blocker and not any(b.startswith(expect_blocker) for b in res["blockers"]):
                raise SystemExit(f"[{label}] falta el bloqueo {expect_blocker}: {res['blockers']}")
            if registry_counter_mismatch and comp == reg["count_complete"]:
                raise SystemExit(f"[{label}] el contador no detectó la mentira: ambos {comp}")
            return res

        # 1. Hand-bumped counter.
        def bump():
            reg = read(root, "analysis/class-registry.json")
            reg["count_complete"] = 1
            write(root, "analysis/class-registry.json", reg)
        expect("contador a mano", bump, expect_verdict="review-required", registry_counter_mismatch=True)

        # 2. Java-only member treated as reachable.
        def reachable():
            report = read(root, "analysis/quartpos-evidence-report.json")
            report["unreachable_java_only"] = []
            write(root, "analysis/quartpos-evidence-report.json", report)
        expect("java-only alcanzable", reachable, expect_verdict="partial", expect_blocker="reflection-gap:<init>()V")

        # 3. Java-only member excluded with no reason.
        def no_reason():
            report = read(root, "analysis/quartpos-evidence-report.json")
            report["unreachable_java_only"][0]["reason"] = "   "
            write(root, "analysis/quartpos-evidence-report.json", report)
        expect("exclusión sin motivo", no_reason, expect_verdict="partial",
               expect_blocker="reflection-gap-without-reason:<init>()V")

        # 4. A declared member left without evidence.
        def drop_member():
            report = read(root, "analysis/quartpos-evidence-report.json")
            report["differential_members"] = [m for m in report["differential_members"]
                                              if m["member"] != "fromBlock(I)I"]
            write(root, "analysis/quartpos-evidence-report.json", report)
        expect("miembro sin evidencia", drop_member, expect_verdict="partial",
               expect_blocker="member-without-evidence:fromBlock(I)I")

        # 5. Evidence invented for a member the classfile does not declare.
        def invent_member():
            report = read(root, "analysis/quartpos-evidence-report.json")
            report["differential_members"].append({"member": "toBlockFromJava(I)I"})
            write(root, "analysis/quartpos-evidence-report.json", report)
        expect("miembro inventado", invent_member, expect_verdict="partial",
               expect_blocker="member-not-in-classfile:toBlockFromJava(I)I")

        # 6. Claiming certification while a blocker exists.
        def claim_with_blocker():
            reg = read(root, "analysis/class-registry.json")
            reg["classes"][0].update({"certified": True, "review": "analysis/x.md", "reviewer": "A"})
            write(root, "analysis/class-registry.json", reg)
            report = read(root, "analysis/quartpos-evidence-report.json")
            report["unreachable_java_only"] = []
            write(root, "analysis/quartpos-evidence-report.json", report)
        res = expect("certificado con bloqueo", claim_with_blocker, expect_verdict="partial",
                     expect_blocker="reflection-gap:<init>()V")
        if "claimed-certified-with-blockers" not in res["blockers"]:
            raise SystemExit("[certificado con bloqueo] no se marcó claimed-certified-with-blockers")

        # 7. The honest complete path: evidence + independent review, counter moves.
        def certify():
            reg = read(root, "analysis/class-registry.json")
            reg["classes"][0].update({"status": "complete", "certified": True,
                                      "review": "analysis/c03-quartpos-class-surface.md",
                                      "reviewer": "B"})
            reg["count_complete"] = 1
            reg["complete"] = ["net/minecraft/core/QuartPos"]
            write(root, "analysis/class-registry.json", reg)
        expect("camino completo honrado", certify, expect_verdict="complete", registry_counter_mismatch=False)

        # 8. Same-hash classfile but a stale class name must not pass.
        def rename():
            manifest = read(root, "analysis/class-evidence/quartpos-classfile.json")
            manifest["class"] = "net/minecraft/core/SectionPos"
            write(root, "analysis/class-evidence/quartpos-classfile.json", manifest)
        expect("manifiesto de otra clase", rename, expect_verdict="partial",
               expect_blocker="class-mismatch:net/minecraft/core/SectionPos")

    print("OK: predicado del contador ejercido — QuartPos queda review-required (0/7.762), "
          "y ocho alteraciones rechazadas: contador a mano, java-only tratado como alcanzable, "
          "exclusión sin motivo, miembro sin evidencia, miembro inventado, certificación con bloqueo, "
          "manifiesto de otra clase; el camino completo honrado sí cuenta (y mueve el contador).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
