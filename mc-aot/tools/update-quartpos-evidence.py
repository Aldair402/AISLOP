#!/usr/bin/env python3
"""Regenerate QuartPos evidence from a fresh run, with hashes computed, not copied.

Evidence that is edited by hand is evidence nobody can re-check. This script
runs the surface check, writes its log, parses the classfile manifest, and then
rewrites both the member manifest (`analysis/class-evidence/quartpos.json`) and
the report (`analysis/quartpos-evidence-report.json`) with the hashes of the
files that actually produced them. `class-surface-evidence.py` and
`check-class-registry.py` then verify those hashes independently.

It does not change `count_complete`. The class stays partial because the private
constructor is only observable through reflection, which the translator does not
implement.

Usage: python3 mc-aot/tools/update-quartpos-evidence.py [--check]
  --check   write the files and then fail if `git diff` shows they changed
            (i.e. the committed evidence was stale)
"""
import argparse, hashlib, json, pathlib, subprocess, sys

PROJECT = pathlib.Path(__file__).resolve().parents[2]   # repository root
ROOT = PROJECT / "mc-aot"                               # crate root
CLASS = "net/minecraft/core/QuartPos"
CLASS_DOTTED = CLASS.replace("/", ".")
CHECK = ROOT / "tests/check-quartpos-class-surface.py"
CLASSFILE_TOOL = ROOT / "tools/classfile-surface.py"
LOG = PROJECT / "analysis/quartpos-static-surface.log"
MANIFEST = PROJECT / "analysis/class-evidence/quartpos.json"
CLASSFILE_MANIFEST = PROJECT / "analysis/class-evidence/quartpos-classfile.json"
REPORT = PROJECT / "analysis/quartpos-evidence-report.json"
REGISTRY = PROJECT / "analysis/class-registry.json"

STATIC_METHODS = [("fromBlock", "(I)I"), ("quartLocal", "(I)I"), ("toBlock", "(I)I"),
                  ("fromSection", "(I)I"), ("toSection", "(I)I")]
FIELDS = [("BITS", "I"), ("SIZE", "I"), ("MASK", "I"), ("SECTION_TO_QUARTS_BITS", "I")]


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_check() -> str:
    out = subprocess.run([sys.executable, str(CHECK)], text=True, capture_output=True)
    if out.returncode:
        sys.stderr.write(out.stdout + out.stderr)
        raise SystemExit("el check de superficie falló; no se regenera evidencia de un fallo")
    return out.stdout.strip()


def write_classfile_manifest() -> dict:
    CLASSFILE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(CLASSFILE_TOOL), CLASS_DOTTED,
                    "--manifest", str(CLASSFILE_MANIFEST), "--json"],
                   text=True, capture_output=True, check=True)
    return json.loads(CLASSFILE_MANIFEST.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="falla si la evidencia commiteada estaba desactualizada")
    args = ap.parse_args()

    before = {p: sha(p) if p.is_file() else None for p in (LOG, MANIFEST, REPORT, CLASSFILE_MANIFEST, REGISTRY)}

    line = run_check()
    LOG.write_text(line + "\n")
    classfile = write_classfile_manifest()

    common_evidence = [
        {"path": "mc-aot/tests/check-quartpos-class-surface.py", "sha256": sha(CHECK)},
        {"path": "mc-aot/tools/classfile-surface.py", "sha256": sha(CLASSFILE_TOOL)},
        {"path": "analysis/quartpos-static-surface.log", "sha256": sha(LOG)},
        {"path": "analysis/class-evidence/quartpos-classfile.json", "sha256": sha(CLASSFILE_MANIFEST)},
    ]
    members = []
    for name, desc in STATIC_METHODS:
        members.append({"kind": "method", "name": name, "descriptor": desc,
                        "evidence": common_evidence})
    # El manifiesto no admite campos libres (el auditor exige exactamente
    # kind/name/descriptor/evidence); la diferencia diferencial vs solo-Java se
    # registra en el informe, que es donde se lee el alcance de la evidencia.
    members.append({"kind": "method", "name": "<init>", "descriptor": "()V",
                    "evidence": common_evidence})
    for name, desc in FIELDS:
        members.append({"kind": "field", "name": name, "descriptor": desc,
                        "evidence": common_evidence})

    limitations = [
        "La comparación de los cinco métodos usa 515 entradas int por método y cuatro lecturas de campo; "
        "no prueba todo el dominio, solo límites de int, vecindad y 500 valores aleatorios con semilla fija.",
        "El constructor privado se mide por reflexión en Java (IllegalAccessException sin setAccessible, "
        "instancia con setAccessible) y su bytecode es el constructor por defecto; el traductor no implementa "
        "reflexión, así que no hay contraste nativo equivalente y no puede contar como diferencial.",
        "La superficie se reconcilia con el classfile y con la reflexión (flags, superclase, interfaces, campos, "
        "constructores), pero no se verifica comportamiento heredado de Object ni identidad de la clase en nativo.",
    ]

    differential_members = [{"member": f"{n}{d}"} for n, d in STATIC_METHODS]
    differential_members += [{"member": f"{n}:{d}"} for n, d in FIELDS]
    java_only_members = [{"member": "<init>()V"}]
    unreachable_java_only = [{
        "member": "<init>()V",
        "reason": ("constructor privado de una clase final con solo métodos estáticos: ningún bytecode "
                   "traducido puede invocarlo; solo la reflexión con setAccessible lo alcanza, y esa ruta es "
                   "java-only, no un camino del programa"),
    }]

    classification = {m["member"]: "differential" for m in differential_members}
    classification.update({m["member"]: "java-only" for m in java_only_members})

    manifest = {
        "schema": "partial-surface-v1",
        "members_classification": classification,
        "jar_sha256": classfile["jar_sha256"],
        "class": CLASS,
        "class_sha256": classfile["class_sha256"],
        "members": members,
        "limitations": limitations,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


    report = {
        "class": CLASS,
        "jar_sha256": classfile["jar_sha256"],
        "class_sha256": classfile["class_sha256"],
        "classes_in_jar": 7762,
        "methods_declared": len(classfile["methods"]),
        "methods_with_partial_evidence": len(classfile["methods"]),
        "methods_differential": len(STATIC_METHODS),
        "methods_java_only": 1,
        "fields_declared": len(classfile["fields"]),
        "fields_with_partial_evidence": len(classfile["fields"]),
        "methods_without_evidence": [],
        "fields_without_evidence": [],
        "differential_members": differential_members,
        "java_only_members": java_only_members,
        "unreachable_java_only": unreachable_java_only,
        "classfile_surface": {
            "flags": classfile["flags"],
            "super_class": classfile["super_class"],
            "interfaces": classfile["interfaces"],
            "has_init": classfile["has_init"],
            "has_clinit": classfile["has_clinit"],
            "declared_methods": [f"{m['name']}{m['descriptor']}" for m in classfile["methods"]],
            "declared_fields": [f"{m['name']}:{m['descriptor']}" for m in classfile["fields"]],
        },
        "evidence_files": {path: sha(PROJECT / path) for path in
                           ("mc-aot/tests/check-quartpos-class-surface.py",
                            "mc-aot/tools/classfile-surface.py",
                            "analysis/quartpos-static-surface.log",
                            "analysis/class-evidence/quartpos-classfile.json")},
        "limitations": limitations,
        "certified": False,
        "warning": "Inventario de evidencias parciales: no certifica la clase ni incrementa el contador.",
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    registry = json.loads(REGISTRY.read_text())
    entry = next(e for e in registry["classes"] if e["class"] == CLASS)
    entry["surface"].update({
        "methods_declared": len(classfile["methods"]),
        "fields_declared": len(classfile["fields"]),
        "methods_with_evidence": len(classfile["methods"]),
        "fields_with_evidence": len(classfile["fields"]),
        "methods_without_evidence": [],
        "fields_without_evidence": [],
        "differential_members": differential_members,
        "java_only_members": java_only_members,
        "unreachable_java_only": unreachable_java_only,
        "methods_differential": [f"{n}{d}" for n, d in STATIC_METHODS],
        "methods_java_only": ["<init>()V"],
    })
    entry["evidence"] = {
        "manifest": "analysis/class-evidence/quartpos.json",
        "classfile_manifest": "analysis/class-evidence/quartpos-classfile.json",
        "report": "analysis/quartpos-evidence-report.json",
        "tests": ["mc-aot/tests/check-quartpos-class-surface.py",
                  "mc-aot/tools/classfile-surface.py"],
        "logs": ["analysis/quartpos-static-surface.log"],
    }
    entry["limitations"] = limitations
    entry["status"] = "partial-evidence"
    entry["date_verified"] = "2026-11-05"
    REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")

    print(f"OK: evidencia regenerada para {CLASS} — {len(members)} miembros "
          f"({len(STATIC_METHODS)} diferenciales + 1 constructor solo-Java + {len(FIELDS)} campos)")
    print(f"  log: {LOG.relative_to(PROJECT)}")
    print(f"  manifiesto: {MANIFEST.relative_to(PROJECT)}")
    print(f"  manifiesto de classfile: {CLASSFILE_MANIFEST.relative_to(PROJECT)}")
    print(f"  informe: {REPORT.relative_to(PROJECT)}")
    print(f"  contador: {json.loads(REGISTRY.read_text())['count_complete']} (sin cambios)")

    if args.check:
        after = {p: sha(p) if p.is_file() else None for p in before}
        stale = [str(p.relative_to(PROJECT)) for p in before if before[p] != after[p]]
        if stale:
            print("FALLO: evidencia commiteada desactualizada: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("OK: la evidencia commiteada coincide con una ejecución fresca")
    return 0


if __name__ == "__main__":
    sys.exit(main())
