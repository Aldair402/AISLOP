#!/usr/bin/env python3
"""Regenerate one class's evidence from a fresh run of its own test.

`update-quartpos-evidence.py` works for exactly one class because it *knows* the
class: the member list, the constructor story and the limitations are written into
the script. That does not scale to 7.762 classes and, worse, it lets the person who
wrote the script decide what the evidence says.

This tool knows nothing about the class. It reads a spec that says *where* things
live and *how* to run the test, then:

1. runs the test, which measures the class and emits what it actually covered
   (`--emit`), and keeps its stdout as the log;
2. reads the classfile manifest, which is the authority on which members exist;
3. refuses to continue if the test claims a member the classfile does not declare,
   or if some declared member is neither measured nor explicitly accounted for as a
   gap with a reason — silence is not a verdict;
4. writes the member manifest, the report and the registry entry with hashes of the
   files that produced them, and never touches `count_complete`.

The split matters: the test measures, the classfile says what exists, this script
only refuses to publish a story that does not add up. Certification is still
somebody else's signature (`class-complete-predicate.py`, R4).

Usage:
  python3 mc-aot/tools/update-class-evidence.py --spec analysis/class-specs/<name>.json
  python3 mc-aot/tools/update-class-evidence.py --spec <name>.json --check
"""
import argparse, hashlib, json, pathlib, subprocess, sys

PROJECT = pathlib.Path(__file__).resolve().parents[2]
ROOT = PROJECT / "mc-aot"
CLASSFILE_TOOL = ROOT / "tools/classfile-surface.py"
REGISTRY = PROJECT / "analysis/class-registry.json"
KINDS = {"differential", "java-only"}


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def die(message):
    print(f"FALLO: {message}", file=sys.stderr)
    raise SystemExit(1)


def member_key(kind, item):
    return f"{item['name']}{item['descriptor']}" if kind == "method" else f"{item['name']}:{item['descriptor']}"


def run_test(spec):
    """Corre el test de la clase y devuelve (stdout, clasificación medida)."""
    test = PROJECT / spec["test"]
    if not test.is_file():
        die(f"el test declarado no existe: {spec['test']}")
    emit = PROJECT / (spec["report"] + ".emit")
    emit.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run([sys.executable, str(test), "--emit", str(emit)],
                         text=True, capture_output=True, cwd=PROJECT)
    emitted = None
    if emit.is_file():
        emitted = json.loads(emit.read_text())
        emit.unlink()
    if out.returncode:
        sys.stderr.write(out.stdout[-2000:] + out.stderr[-2000:])
        die("el test de la clase falló; no se regenera evidencia de un fallo")
    if emitted is None:
        die("el test no emitió clasificación; sin medición no hay evidencia")
    return out.stdout.strip(), emitted


def classfile_manifest(spec):
    target = PROJECT / spec["classfile_manifest"]
    target.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run([sys.executable, str(CLASSFILE_TOOL), spec["class"].replace("/", "."),
                          "--manifest", str(target), "--json"],
                         text=True, capture_output=True, cwd=PROJECT)
    if out.returncode:
        sys.stderr.write(out.stdout[-1000:] + out.stderr[-1000:])
        die("no se pudo leer el classfile")
    return json.loads(target.read_text())


def validate_spec(spec):
    """El spec tiene que decir dónde vive cada cosa y qué límites tiene la evidencia."""
    for key in ("class", "test", "log", "manifest", "classfile_manifest", "report", "limitations"):
        if key not in spec:
            die(f"el spec no declara `{key}`")
    limits = spec["limitations"]
    if not isinstance(limits, list) or not limits or not all(str(x).strip() for x in limits):
        die("el spec tiene que declarar limitaciones: una clase sin límites no existe")
    return spec


def validate_kinds(measured):
    for member, kind in measured.items():
        if kind not in KINDS:
            die(f"tipo de evidencia no aceptado: {member}={kind}")
    return measured


def check_accounting(declared, measured, gaps):
    """Todo miembro declarado está medido o declarado como hueco con motivo."""
    unaccounted = sorted(declared - set(measured) - set(gaps))
    if unaccounted:
        die("miembros sin evidencia y sin motivo declarado: " + ", ".join(unaccounted))
    invented = sorted((set(measured) | set(gaps)) - declared)
    if invented:
        die("el test declara miembros que el classfile no declara: " + ", ".join(invented))
    without_reason = sorted(m for m, reason in gaps.items() if not str(reason).strip())
    if without_reason:
        die("huecos declarados sin motivo: " + ", ".join(without_reason))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True, type=pathlib.Path)
    ap.add_argument("--check", action="store_true",
                    help="falla si la evidencia commiteada estaba desactualizada")
    args = ap.parse_args()

    spec_path = args.spec if args.spec.is_absolute() else PROJECT / args.spec
    spec = validate_spec(json.loads(spec_path.read_text()))

    outputs = [PROJECT / spec["log"], PROJECT / spec["manifest"],
               PROJECT / spec["classfile_manifest"], PROJECT / spec["report"], REGISTRY]
    before = {p: sha(p) if p.is_file() else None for p in outputs}

    log_text, emitted = run_test(spec)
    if emitted is None:
        die("el test no emitió clasificación; sin medición no hay evidencia")
    if emitted["class"] != spec["class"]:
        die(f"el test mide {emitted['class']} y el spec declara {spec['class']}")

    classfile = classfile_manifest(spec)
    if classfile["class"] != spec["class"]:
        die(f"el manifiesto de classfile es de {classfile['class']}")

    declared = {member_key("method", m) for m in classfile["methods"]} | \
               {member_key("field", f) for f in classfile["fields"]}
    measured = {}
    for item in emitted.get("differential_members", []):
        measured[item["member"]] = "differential"
    for item in emitted.get("java_only_members", []):
        measured[item["member"]] = "java-only"
    gaps = {item["member"]: item.get("reason", "") for item in emitted.get("reflection_gap_members", [])}
    validate_kinds(measured)
    check_accounting(declared, measured, gaps)

    log_path = PROJECT / spec["log"]
    log_path.write_text(log_text + "\n")
    evidence_files = [
        {"path": spec["test"], "sha256": sha(PROJECT / spec["test"])},
        {"path": "mc-aot/tools/classfile-surface.py", "sha256": sha(CLASSFILE_TOOL)},
        {"path": spec["log"], "sha256": sha(log_path)},
        {"path": spec["classfile_manifest"], "sha256": sha(PROJECT / spec["classfile_manifest"])},
    ]
    members = []
    for entry in classfile["methods"]:
        members.append({"kind": "method", "name": entry["name"], "descriptor": entry["descriptor"],
                        "evidence": evidence_files})
    for entry in classfile["fields"]:
        members.append({"kind": "field", "name": entry["name"], "descriptor": entry["descriptor"],
                        "evidence": evidence_files})
    manifest = {
        "schema": "partial-surface-v1",
        "members_classification": measured,
        "jar_sha256": classfile["jar_sha256"],
        "class": spec["class"],
        "class_sha256": classfile["class_sha256"],
        "members": members,
        "limitations": spec["limitations"],
    }
    manifest_path = PROJECT / spec["manifest"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    differential = [{"member": m, "cases": next((i.get("cases") for i in emitted["differential_members"]
                                                 if i["member"] == m), None)}
                    for m, kind in measured.items() if kind == "differential"]
    java_only = [m for m, kind in measured.items() if kind == "java-only"]
    report = {
        "class": spec["class"],
        "jar_sha256": classfile["jar_sha256"],
        "class_sha256": classfile["class_sha256"],
        "methods_declared": len(classfile["methods"]),
        "methods_with_partial_evidence": sum(1 for m in classfile["methods"]
                                             if member_key("method", m) in measured),
        "methods_differential": sum(1 for m in classfile["methods"]
                                    if measured.get(member_key("method", m)) == "differential"),
        "methods_java_only": sum(1 for m in classfile["methods"]
                                 if measured.get(member_key("method", m)) == "java-only"),
        "fields_declared": len(classfile["fields"]),
        "fields_with_partial_evidence": sum(1 for f in classfile["fields"]
                                            if member_key("field", f) in measured),
        "differential_members": differential,
        "java_only_members": [{"member": m} for m in java_only],
        "unreachable_java_only": [{"member": m, "reason": gaps[m]} for m in java_only if gaps.get(m)],
        "reflection_gap_members": [{"member": m, "reason": r} for m, r in gaps.items()],
        "results": emitted.get("results"),
        "cross_dependencies": emitted.get("cross_dependencies", []),
        "classfile_surface": {
            "flags": classfile["flags"],
            "super_class": classfile["super_class"],
            "interfaces": classfile["interfaces"],
            "has_init": classfile["has_init"],
            "has_clinit": classfile["has_clinit"],
            "declared_methods": [f"{m['name']}{m['descriptor']}" for m in classfile["methods"]],
            "declared_fields": [f"{f['name']}:{f['descriptor']}" for f in classfile["fields"]],
        },
        "evidence_files": {entry["path"]: entry["sha256"] for entry in evidence_files},
        "limitations": spec["limitations"],
        "certified": False,
        "warning": "Inventario de evidencias parciales: no certifica la clase ni incrementa el contador.",
    }
    (PROJECT / spec["report"]).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    registry = json.loads(REGISTRY.read_text())
    entry = next((e for e in registry["classes"] if e["class"] == spec["class"]), None)
    new_entry = {
        "class": spec["class"],
        "status": "partial-evidence",
        "jar_sha256": classfile["jar_sha256"],
        "class_sha256": classfile["class_sha256"],
        "surface": {
            "methods_declared": len(classfile["methods"]),
            "fields_declared": len(classfile["fields"]),
            "methods_with_evidence": report["methods_with_partial_evidence"],
            "fields_with_evidence": report["fields_with_partial_evidence"],
            "methods_without_evidence": sorted(m for m in declared
                                               if m not in measured and m not in gaps),
            "fields_without_evidence": sorted(f for f in declared
                                              if f not in measured and f not in gaps),
            "differential_members": [dict(item) for item in differential],
            "java_only_members": [dict(item) for item in report["java_only_members"]],
            "unreachable_java_only": [dict(item) for item in report["unreachable_java_only"]],
        },
        "evidence": {
            "manifest": spec["manifest"],
            "classfile_manifest": spec["classfile_manifest"],
            "report": spec["report"],
            "tests": [spec["test"], "mc-aot/tools/classfile-surface.py"],
            "logs": [spec["log"]],
        },
        "limitations": spec["limitations"],
        "certified": False,
        "review": None,
        "reviewer": None,
        "date_verified": spec.get("date_verified", "2026-11-05"),
    }
    if entry is None:
        registry["classes"].append(new_entry)
        registry["classes"].sort(key=lambda e: e["class"])
    elif (entry.get("status") not in (None, "partial-evidence")
          or entry.get("certified") or entry.get("review") or entry.get("reviewer")):
        # Si otro frente firmó la clase, el registro se conserva **tal cual**: esta
        # herramienta no es quién para borrar una firma (ni estado, ni fecha ni
        # revisión) ni para inventar una. La evidencia derivada (reporte, manifiesto
        # y log) sí se regenera y `--check` la compara byte a byte; con evidencia
        # fresca idéntica, el registro no cambia y la comprobación pasa.
        pass
    else:
        entry.clear()
        entry.update(new_entry)
    REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")

    print(f"OK: evidencia regenerada para {spec['class']} — {len(measured)}/{len(declared)} miembros "
          f"con evidencia medida ({len(differential)} diferenciales, {len(java_only)} solo-Java, "
          f"{len(gaps)} huecos declarados)")
    print(f"  log: {spec['log']}")
    print(f"  manifiesto: {spec['manifest']}")
    print(f"  informe: {spec['report']}")
    print(f"  contador: {registry['count_complete']} (sin cambios)")

    if args.check:
        after = {p: sha(p) if p.is_file() else None for p in outputs}
        stale = [str(p.relative_to(PROJECT)) for p in outputs if before[p] != after[p]]
        if stale:
            print("FALLO: evidencia commiteada desactualizada: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("OK: la evidencia commiteada coincide con una ejecución fresca")
    return 0


if __name__ == "__main__":
    sys.exit(main())
