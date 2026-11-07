#!/usr/bin/env python3
"""A-02 phase 2, step 1: say *why* no vanilla class reaches the bridge layout.

The old number was "0 of 687 candidates". That number says nothing about what
to do next: it does not distinguish a class that fails one clause from a class
that fails six. This census parses every classfile in the official JAR with the
same pure-Python parser that `classfile-surface.py` uses (no JDK, no Rust
binary) and applies the profile clauses of `numeric_bridge_layout.verify`
literally, recording every clause each class violates -- not only the first.

With that, "0/7762" becomes a work list: how many classes fail on the exact
set {statics}, {statics, <clinit>}, {descriptor}, and so on. A relaxation is
worth writing only if it unlocks real classes, so the census also simulates
relaxations and reports how many classes each one adds.

Usage:
  python3 mc-aot/tools/layout-profile-census.py                      # resumen
  python3 mc-aot/tools/layout-profile-census.py --json out.json      # censo completo
  python3 mc-aot/tools/layout-profile-census.py --simulate            # valorar relajaciones
  python3 mc-aot/tools/layout-profile-census.py --class net.minecraft.core.QuartPos

Exit codes: 0 census produced; 2 JAR missing or unreadable.
"""
import argparse
import collections
import importlib.util
import json
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
JAR = ROOT / "downloads" / "server-26.3-inner.jar"
SURFACE = pathlib.Path(__file__).with_name("classfile-surface.py")

# Igual que numeric_bridge_layout.NAME: el perfil no acepta nombres fuera de
# net/minecraft, ni `$` anónimos de más de un nivel por clase anidada.
NAME = re.compile(r'net/minecraft/(?:[A-Za-z0-9_$]+/)*[A-Za-z0-9_$]+\Z')
SUPPORTED = {"I"}
FIELD_ACC = {"static": 0x0008, "final": 0x0010, "volatile": 0x0040,
             "transient": 0x0080, "synthetic": 0x1000, "enum": 0x4000}
CLASS_ACC = {"final": 0x0010, "interface": 0x0200, "abstract": 0x0400,
             "annotation": 0x2000, "enum": 0x4000, "module": 0x8000}


def load_parser():
    spec = importlib.util.spec_from_file_location("classfile_surface", SURFACE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blockers(surface, allow_mutable_refs=False, relax=frozenset(), extended=frozenset()):
    """Cláusulas del perfil que la clase viola, en el orden del verificador.

    `clase-no-final` ya no significa «no es `final`»: significa «no es un tipo
    cerrado», es decir, o no es `final` o alguna clase del JAR la extiende. Es lo
    que hace `numeric_bridge_layout.verify` desde el 2026-11-06.
    """
    out = []
    flags = surface["flag_bits"]
    name = surface["this_class"]
    if "name" not in relax and not NAME.match(name):
        out.append("nombre-fuera-del-perfil")
    if "final" not in relax and not flags & CLASS_ACC["final"] and name in extended:
        out.append("clase-no-final")
    if any(flags & CLASS_ACC[k] for k in ("interface", "abstract", "annotation", "enum")):
        out.append("clase-abstracta/interfaz/enum")
    if "super" not in relax and surface["super_class"] != "java/lang/Object":
        out.append("superclase")
    if "interfaces" not in relax and surface["interfaces"]:
        out.append("interfaces")
    if "clinit" not in relax and surface["has_clinit"]:
        out.append("clinit")
    descriptors = set()
    for field in surface["fields"]:
        acc = field["flag_bits"]
        descriptor = field["descriptor"]
        if acc & FIELD_ACC["static"] and "statics" not in relax:
            out.append("estaticos")
        if acc & FIELD_ACC["volatile"]:
            out.append("volatile")
        if descriptor in SUPPORTED:
            if acc & FIELD_ACC["final"]:
                out.append("int-final")
        elif descriptor.startswith("L") and descriptor.endswith(";"):
            target = descriptor[1:-1]
            if not acc & FIELD_ACC["final"] and not allow_mutable_refs:
                out.append("ref-no-final")
            if not NAME.match(target):
                out.append("ref-fuera-del-perfil")
        else:
            descriptors.add(descriptor)
    if descriptors and "descriptor" not in relax:
        out.append("descriptor")
    # Orden estable y sin repetidos: un censo que cambia de orden no se compara.
    seen, ordered = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def census(jar, allow_mutable_refs):
    parser = load_parser()
    rows = []
    with zipfile.ZipFile(jar) as z:
        entries = [n for n in z.namelist()
                   if n.endswith(".class") and not n.startswith("META-INF/")]
        parsed = [(entry, parser.parse_class(z.read(entry))) for entry in sorted(entries)]
        # Jerarquía del mundo cerrado: quién es extendido por otra clase del JAR.
        extended = {surface["super_class"] for _, surface in parsed if surface["super_class"]}
        for entry, surface in parsed:
            instance = [f for f in surface["fields"] if not f["flag_bits"] & 0x0008]
            refs = sorted({f["descriptor"][1:-1] for f in surface["fields"]
                           if f["descriptor"].startswith("L")})
            inst_refs = sorted({f["descriptor"][1:-1] for f in instance
                                if f["descriptor"].startswith("L")})
            rows.append({
                "class": surface["this_class"],
                "entry": entry,
                "fields": len(surface["fields"]),
                "descriptor_set": sorted({f["descriptor"] for f in surface["fields"]}),
                "ref_targets": refs,
                "super": surface["super_class"],
                "interfaces": surface["interfaces"],
                "instance_fields": len(instance),
                "instance_refs": inst_refs,
                "instance_descriptors": sorted({f["descriptor"] for f in instance}),
                "static_fields": len(surface["fields"]) - len(instance),
                "blockers": blockers(surface, allow_mutable_refs, frozenset(), extended),
                "has_clinit": surface["has_clinit"],
            })
    return rows


def summarize(rows):
    total = len(rows)
    admitted = [r for r in rows if not r["blockers"]]
    first = collections.Counter(r["blockers"][0] for r in rows if r["blockers"])
    anywhere = collections.Counter(b for r in rows for b in r["blockers"])
    single = collections.Counter(r["blockers"][0] for r in rows if len(r["blockers"]) == 1)
    combos = collections.Counter("+".join(r["blockers"]) for r in rows if r["blockers"])
    return {"total": total, "admitted": admitted, "first_blocker": first,
            "anywhere": anywhere, "single_blocker": single, "combos": combos}


def simulate(rows, mutable):
    """Cuántas clases adicionales abre cada relajación por sí sola."""
    relaxations = {
        "estaticos (solo estáticos compartidos)": frozenset({"statics"}),
        "clinit": frozenset({"clinit"}),
        "descriptor (J/F/D/Z/B/C/S)": frozenset({"descriptor"}),
        "refs no finales (opt-in MutRef)": None,  # se simula aparte
        "clase-no-final": frozenset({"final"}),
        "superclase": frozenset({"super"}),
    }
    base = len(closure_admitted(rows))
    out = {}
    for label, relax in relaxations.items():
        if relax is None:
            out[label] = len(closure_admitted(rows, frozenset({"ref-no-final"}))) - base
            continue
        out[label] = len(closure_admitted(rows, relax)) - base
    # Combinaciones, que es como se cierra un perfil real.
    pairs = {}
    keys = [frozenset({"statics"}), frozenset({"clinit"}), frozenset({"descriptor"}),
            frozenset({"final"}), frozenset({"super"})]
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            pairs["+".join(sorted(a | b))] = len(closure_admitted(rows, a | b)) - base
    return {"base": base, "single": out, "pairs": pairs}


RELAX_TO_CLAUSE = {"statics": "estaticos", "clinit": "clinit", "descriptor": "descriptor",
                   "final": "clase-no-final", "super": "superclase",
                   "interfaces": "interfaces", "name": "nombre-fuera-del-perfil",
                   "ref-no-final": "ref-no-final"}


def blockers_for(row, relax):
    """Cláusulas que quedan cuando se conceden las relajaciones `relax`."""
    clauses = {RELAX_TO_CLAUSE[r] for r in relax}
    return [b for b in row["blockers"] if b not in clauses]


def closed_world_final(rows):
    """Clases que nadie extiende dentro del JAR: cerradas aunque no sean `final`."""
    parents = collections.Counter(r["super"] for r in rows if r["super"])
    return {r["class"] for r in rows if parents.get(r["class"], 0) == 0}


def closure_admitted(rows, relax=frozenset()):
    """Clases cuyo grafo entero de referencias cabe en el perfil.

    Un layout no sirve si el campo apunta a una clase que el perfil no admite:
    el verificador cierra el grafo y rechaza la raíz. Por eso el censo por
    clase (arriba) es una cota superior y este fixpoint es el número real.
    """
    valid = {r["class"] for r in rows if not blockers_for(r, relax)}
    by_class = {r["class"]: r for r in rows}
    changed = True
    while changed:
        changed = False
        for klass in list(valid):
            row = by_class[klass]
            targets = row["ref_targets"]
            if any(t not in valid for t in targets):
                valid.discard(klass)
                changed = True
    return valid


def structural_blockers(row, closed, relax=frozenset()):
    """Cláusulas que hablan del **estado de instancia** de la clase.

    `estaticos` y `clinit` no describen el layout de un objeto: son capacidad de
    ejecución (A-05). `interfaces` tampoco: afectan al despacho, no a los campos.
    Separarlas convierte "no entra en el perfil" en "el layout se puede escribir,
    pero la clase todavía no se puede ejecutar", que es lo que de verdad pasa.
    """
    out = []
    if "final" in relax:
        # Sólo para comparar escenarios antiguos: hoy el perfil ya cierra por
        # ausencia de subclases.
        if row["class"] in closed and "clase-no-final" in row["blockers"]:
            pass
        elif "clase-no-final" in row["blockers"]:
            out.append("clase-no-final")
    elif "clase-no-final" in row["blockers"]:
        out.append("clase-no-final")
    for clause in ("nombre-fuera-del-perfil", "superclase", "ref-fuera-del-perfil",
                   "ref-no-final", "int-final", "volatile", "descriptor"):
        if clause == "superclase" and "super" in relax:
            continue
        if clause == "interfaces":
            continue
        if clause in row["blockers"]:
            out.append(clause)
    if "interfaces" not in relax and row["interfaces"]:
        out.append("interfaces")
    return out


def plan(rows):
    """Qué compra cada relajación, en clases y en campos reales."""
    closed = closed_world_final(rows)
    by = {r["class"]: r for r in rows}
    steps = [
        ("perfil actual de `numeric_bridge_layout.verify`", frozenset()),
        ("+ estáticos y `clinit` fuera del criterio de layout", frozenset({"statics", "clinit"})),
        ("+ interfaces fuera del criterio de layout",
         frozenset({"statics", "clinit", "interfaces"})),
        ("+ refs de instancia sin cierre (layout del destino bajo demanda)",
         frozenset({"statics", "clinit", "interfaces"})),
    ]

    def admitted(relax, require_closure):
        """La supercadena se exige siempre: un layout sin los campos del padre miente."""
        valid = {r["class"] for r in rows
                 if not blockers_for(r, relax) and not structural_blockers(r, closed, relax)}
        changed = True
        while changed:
            changed = False
            for klass in list(valid):
                row = by[klass]
                sup = row["super"]
                if sup != "java/lang/Object" and sup not in valid:
                    valid.discard(klass)
                    changed = True
                elif require_closure and any(t not in valid for t in row["instance_refs"]):
                    valid.discard(klass)
                    changed = True
        return valid

    out = []
    for label, relax in steps:
        closure = "sin cierre" not in label
        valid = admitted(relax, closure)
        fields = sum(by[k]["instance_fields"] for k in valid)
        with_fields = sum(1 for k in valid if by[k]["instance_fields"] > 0)
        out.append({"step": label, "classes": len(valid),
                    "classes_with_fields": with_fields, "instance_fields": fields})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jar", type=pathlib.Path, default=JAR)
    ap.add_argument("--json", type=pathlib.Path)
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--allow-mutable-refs", action="store_true")
    ap.add_argument("--class", dest="klass", help="detalle de una clase")
    ap.add_argument("--limit", type=int, default=20, help="filas del top de combinaciones")
    ap.add_argument("--plan", action="store_true", help="qué compra cada relajación")
    args = ap.parse_args()

    if not args.jar.is_file():
        print(f"ERROR: {args.jar} no existe", file=sys.stderr)
        return 2
    rows = census(args.jar, args.allow_mutable_refs)

    if args.klass:
        wanted = args.klass.replace(".", "/")
        hits = [r for r in rows if r["class"] == wanted]
        if not hits:
            print(f"ERROR: {wanted} no está en el JAR", file=sys.stderr)
            return 1
        print(json.dumps(hits[0], indent=2, ensure_ascii=False))
        return 0

    s = summarize(rows)
    print(f"clases en el JAR: {s['total']}")
    print(f"sin bloqueos propios (cota superior): {len(s['admitted'])}")
    closed = closure_admitted(rows)
    print(f"admitidas con el grafo de referencias cerrado: {len(closed)}")
    for klass in sorted(closed):
        print(f"  {klass}")
    print("\nprimer bloqueo (una clase puede violar más):")
    for clause, count in s["first_blocker"].most_common():
        print(f"  {count:6d}  {clause}")
    print("\nclases que violan SOLO esa cláusula (lo que abriría una relajación):")
    for clause, count in s["single_blocker"].most_common():
        print(f"  {count:6d}  {clause}")
    print(f"\ncombinaciones más frecuentes (top {args.limit}):")
    for combo, count in s["combos"].most_common(args.limit):
        print(f"  {count:6d}  {combo}")

    if args.simulate:
        sim = simulate(rows, args.allow_mutable_refs)
        print("\nsimulación de relajaciones (clases admitidas de más):")
        print(f"  base: {sim['base']}")
        for label, gain in sim["single"].items():
            print(f"  solo {label}: +{gain}")
        for label, gain in sim["pairs"].items():
            print(f"  {label}: +{gain}")

    if args.plan:
        print("\nplan medido (clases / clases con campos / campos de instancia):")
        for step in plan(rows):
            print(f"  {step['classes']:5d} / {step['classes_with_fields']:5d} / "
                  f"{step['instance_fields']:6d}  {step['step']}")

    if args.json:
        payload = {"schema": "layout-profile-census-v1",
                   "jar": str(args.jar.name),
                   "allow_mutable_refs": args.allow_mutable_refs,
                   "total": s["total"],
                   "admitted": [r["class"] for r in s["admitted"]],
                   "first_blocker": dict(s["first_blocker"]),
                   "anywhere": dict(s["anywhere"]),
                   "single_blocker": dict(s["single_blocker"]),
                   "combos": dict(s["combos"]),
                   "classes": rows}
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
