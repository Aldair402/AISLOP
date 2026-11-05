#!/usr/bin/env python3
"""The executable predicate behind `count_complete`. One definition, not two.

Q-AC-5 (A to C): "publish the executable predicate the counter uses — which
members count, what evidence satisfies it, what disqualifies a class — in a file
with a test that exercises it". This is that file. The registry counter is not a
number somebody edits by hand: it is the number of classes this script calls
`complete`, and `check-class-complete-predicate.py` fails when they disagree.

Rules, all sourced from ROADMAP.md §5 and the written decisions of the
2026-11-05 discussion (Q-AC-8 from A, Q-BC-* from B):

R1 Surface reconciled.  The members declared in the classfile manifest
   (`analysis/class-evidence/<class>-classfile.json`) must equal the members the
   report claims to cover. A member declared by the JVM and missing from the
   report, or a member invented by the report, blocks the class.
R2 Every member needs evidence of a declared kind: `differential` (Java 25 vs
   native, byte-identical output) or `java-only` (measured only in the JVM).
   Anything else is `member-without-evidence`.
R3 A `java-only` member may only be excluded from certification when it is
   **unreachable without reflection** and the report says why. If it is
   reachable, the class gets `reflection-gap` and stays partial — this is A's
   condition 1: "no lo llama nadie" is not the same as "lo llama algo que no
   modelamos".
R4 A class can only be `complete` with a review from another front: `review` and
   `reviewer` non-null, plus `certified: true`. Same front cannot certify itself.
R5 The registry counter equals the number of `complete` verdicts computed here.
   A hand-edited counter is a failure, not a warning.

Verdicts: `complete` (counts), `review-required` (surface and evidence are
enough, nobody has reviewed it yet), `partial` (a blocker in R1/R2/R3).
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "analysis/class-registry.json"

EVIDENCE_KINDS = {"differential", "java-only"}


def member_key(kind, item):
    name, descriptor = item["name"], item["descriptor"]
    return f"{name}{descriptor}" if kind == "method" else f"{name}:{descriptor}"


def declared_members(classfile_manifest):
    methods = {member_key("method", m) for m in classfile_manifest["methods"]}
    fields = {member_key("field", f) for f in classfile_manifest["fields"]}
    return methods, fields


def coverage(report):
    """Map member -> evidence kind, from the report the last run produced."""
    kinds = {}
    for item in report.get("differential_members", []):
        kinds[item["member"]] = "differential"
    for item in report.get("java_only_members", []):
        kinds[item["member"]] = "java-only"
    return kinds


def judge(entry, project_root=ROOT):
    """Return (verdict, blockers, notes) for one registry entry."""
    blockers, notes = [], []
    evidence = entry.get("evidence", {})
    classfile_rel = evidence.get("classfile_manifest")
    report_rel = evidence.get("report")

    if not classfile_rel or not report_rel:
        return "partial", ["missing-evidence-pointers"], notes
    classfile_path = project_root / classfile_rel
    report_path = project_root / report_rel
    for path, label in ((classfile_path, "classfile-manifest"), (report_path, "report")):
        if not path.is_file():
            blockers.append(f"missing-{label}:{path.relative_to(project_root)}")
    if blockers:
        return "partial", blockers, notes

    classfile = json.loads(classfile_path.read_text())
    report = json.loads(report_path.read_text())

    if classfile["class"] != entry["class"].replace("/", "/"):
        blockers.append(f"class-mismatch:{classfile['class']}")
    if classfile["class_sha256"] != entry["class_sha256"]:
        blockers.append("classfile-hash-mismatch")

    # R1 — the classfile is the authority on what exists.
    declared_methods, declared_fields = declared_members(classfile)
    kinds = coverage(report)
    for missing in sorted(declared_methods - set(kinds)):
        blockers.append(f"member-without-evidence:{missing}")
    for missing in sorted(declared_fields - set(kinds)):
        blockers.append(f"member-without-evidence:{missing}")
    for invented in sorted(set(kinds) - declared_methods - declared_fields):
        blockers.append(f"member-not-in-classfile:{invented}")

    # R2 — every reported kind must be one we accept.
    for member, kind in kinds.items():
        if kind not in EVIDENCE_KINDS:
            blockers.append(f"unknown-evidence-kind:{member}={kind}")

    # R3 — java-only may only be excluded when unreachable without reflection.
    unreachable = {item["member"]: item.get("reason", "") for item in report.get("unreachable_java_only", [])}
    for member, kind in kinds.items():
        if kind != "java-only":
            continue
        if member not in unreachable:
            blockers.append(f"reflection-gap:{member}")
        elif not unreachable[member].strip():
            blockers.append(f"reflection-gap-without-reason:{member}")
        else:
            notes.append(f"java-only-unreachable:{member} ({unreachable[member]})")

    # The claim that matters is the registry entry's, not the evidence file's.
    if entry.get("certified") is True and blockers:
        blockers.append("claimed-certified-with-blockers")
    if report.get("certified") is True and blockers:
        blockers.append("evidence-claims-certification-with-blockers")

    # R4 — independent review.
    review_blockers = []
    if not entry.get("review"):
        review_blockers.append("no-review")
    if not entry.get("reviewer"):
        review_blockers.append("no-reviewer")
    if entry.get("certified") is not True:
        review_blockers.append("not-certified")

    if blockers:
        return "partial", blockers, notes
    if review_blockers:
        return "review-required", review_blockers, notes
    return "complete", [], notes


def evaluate(registry_path=REGISTRY, project_root=None):
    project_root = project_root or registry_path.parents[1]
    registry = json.loads(registry_path.read_text())
    results = []
    for entry in registry["classes"]:
        verdict, blockers, notes = judge(entry, project_root)
        results.append({"class": entry["class"], "declared_status": entry["status"],
                        "verdict": verdict, "blockers": blockers, "notes": notes})
    computed = sum(1 for r in results if r["verdict"] == "complete")
    return registry, results, computed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=pathlib.Path, default=REGISTRY)
    ap.add_argument("--class", dest="only", help="restrict output to one class")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    registry, results, computed = evaluate(args.registry)
    if args.only:
        results = [r for r in results if r["class"] == args.only.replace(".", "/")]

    if args.json:
        print(json.dumps({"count_complete": computed, "classes": results}, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"{r['class']}: {r['verdict']} (status declarado: {r['declared_status']})")
            for note in r["notes"]:
                print(f"    nota: {note}")
            for blocker in r["blockers"]:
                print(f"    bloqueo: {blocker}")
        print(f"count_complete calculado: {computed} · registrado: {registry['count_complete']}")

    if computed != registry["count_complete"]:
        print(f"FALLO: count_complete del registro ({registry['count_complete']}) != predicado ({computed})",
              file=sys.stderr)
        return 1
    pending = [r["class"] for r in results if r["verdict"] == "review-required"]
    if pending:
        print(f"AVISO: listas para revisión, aún sin contar: {', '.join(pending)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
