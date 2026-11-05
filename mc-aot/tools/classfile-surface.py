#!/usr/bin/env python3
"""Parse a classfile's declared surface straight from the JAR, with no JDK.

Why this exists: criterion 1 of ROADMAP §5 asks for the declared surface to be
reconciled with the classfile, including private and synthetic members,
`<clinit>`, flags, superclass and interfaces. Until now that reconciliation was
done by hand and written into the registry, which is exactly the kind of number
that drifts. This script reads the classfile itself and prints what is really
there, so the registry can be checked against bytes instead of notes.

Usage:
  python3 mc-aot/tools/classfile-surface.py net/minecraft/core/QuartPos
  python3 mc-aot/tools/classfile-surface.py net/minecraft/core/QuartPos --json
  python3 mc-aot/tools/classfile-surface.py net/minecraft/core/QuartPos \
      --registry analysis/class-registry.json     # fails on any mismatch

Exit codes: 0 surface printed (and matched, with --registry); 1 mismatch or bad
input; 2 JAR not present.
"""
import argparse, hashlib, json, pathlib, struct, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
JAR = ROOT / "downloads" / "server-26.3-inner.jar"

ACC = {
    0x0001: "public", 0x0002: "private", 0x0004: "protected", 0x0008: "static",
    0x0010: "final", 0x0020: "synchronized" if False else "super", 0x0040: "volatile/bridge",
    0x0080: "transient/varargs", 0x0100: "native", 0x0200: "interface", 0x0400: "abstract",
    0x0800: "strict", 0x1000: "synthetic", 0x2000: "annotation", 0x4000: "enum",
    0x8000: "module",
}
FIELD_FLAGS = {0x0001: "public", 0x0002: "private", 0x0004: "protected", 0x0008: "static",
               0x0010: "final", 0x0040: "volatile", 0x0080: "transient",
               0x1000: "synthetic", 0x4000: "enum"}
METHOD_FLAGS = {0x0001: "public", 0x0002: "private", 0x0004: "protected", 0x0008: "static",
                0x0010: "final", 0x0020: "synchronized", 0x0040: "bridge",
                0x0080: "varargs", 0x0100: "native", 0x0400: "abstract",
                0x0800: "strict", 0x1000: "synthetic"}
CLASS_FLAGS = {0x0001: "public", 0x0010: "final", 0x0020: "super", 0x0200: "interface",
               0x0400: "abstract", 0x1000: "synthetic", 0x2000: "annotation",
               0x4000: "enum", 0x8000: "module"}


def flags(value, table):
    out = [name for bit, name in sorted(table.items()) if value & bit]
    rest = value & ~sum(table)
    if rest:
        out.append(f"0x{rest:04x}")
    return out


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def u1(self):
        v = self.data[self.pos]; self.pos += 1; return v

    def u2(self):
        v = struct.unpack_from(">H", self.data, self.pos)[0]; self.pos += 2; return v

    def u4(self):
        v = struct.unpack_from(">I", self.data, self.pos)[0]; self.pos += 4; return v

    def take(self, n):
        v = self.data[self.pos:self.pos + n]; self.pos += n; return v


def parse_constant_pool(r):
    count = r.u2()
    pool, i = {}, 1
    while i < count:
        tag = r.u1()
        if tag == 1:      # Utf8
            pool[i] = ("utf8", r.take(r.u2()).decode("utf-8", "replace"))
        elif tag in (7, 8, 16, 19, 20):   # Class, String, MethodType, Module, Package
            pool[i] = ("ref", r.u2())
        elif tag in (3, 4):               # Integer, Float
            pool[i] = ("num", r.u4())
        elif tag in (5, 6):               # Long, Double (take two slots)
            pool[i] = ("wide", r.u4() << 32 | r.u4()); i += 1
        elif tag in (9, 10, 11, 12, 17, 18):  # refs and NameAndType-ish
            pool[i] = ("pair", (r.u2(), r.u2()))
        elif tag == 15:                   # MethodHandle
            pool[i] = ("mh", (r.u1(), r.u2()))
        else:
            raise ValueError(f"unknown constant pool tag {tag} at entry {i}")
        i += 1
    return pool


def utf8(pool, index):
    kind, value = pool.get(index, ("missing", None))
    return value if kind == "utf8" else f"<#{index}>"


def class_name(pool, index):
    kind, value = pool.get(index, ("missing", None))
    return utf8(pool, value) if kind == "ref" else f"<#{index}>"


def parse_attributes(r, pool):
    out = {}
    for _ in range(r.u2()):
        name = utf8(pool, r.u2())
        length = r.u4()
        body = r.take(length)
        if name == "ConstantValue" and length == 2:
            out[name] = utf8(pool, struct.unpack(">H", body)[0]) if False else struct.unpack(">H", body)[0]
            kind, value = pool.get(out[name], ("missing", None))
            out[name] = value if kind == "num" else f"<#{out[name]}>"
        else:
            out.setdefault(name, True)
    return out


def parse_class(data):
    r = Reader(data)
    if r.u4() != 0xCAFEBABE:
        raise ValueError("not a classfile")
    r.u2(), r.u2()                      # minor, major
    pool = parse_constant_pool(r)
    access = r.u2()
    this_id, super_id = r.u2(), r.u2()
    interfaces = [class_name(pool, r.u2()) for _ in range(r.u2())]

    def members(kind):
        items = []
        for _ in range(r.u2()):
            acc = r.u2()
            items.append({
                "kind": kind,
                "name": utf8(pool, r.u2()),
                "descriptor": utf8(pool, r.u2()),
                "flags": flags(acc, FIELD_FLAGS if kind == "field" else METHOD_FLAGS),
                "flag_bits": acc,
                "attributes": parse_attributes(r, pool),
            })
        return items

    fields, methods = members("field"), members("method")
    class_attrs = parse_attributes(r, pool)
    return {
        "this_class": class_name(pool, this_id),
        "super_class": class_name(pool, super_id) if super_id else None,
        "interfaces": interfaces,
        "flags": flags(access, CLASS_FLAGS),
        "flag_bits": access,
        "major": struct.unpack_from(">H", data, 6)[0],
        "fields": fields,
        "methods": methods,
        "attributes": sorted(class_attrs),
        "has_clinit": any(m["name"] == "<clinit>" for m in methods),
        "has_init": any(m["name"] == "<init>" for m in methods),
    }


def member_key(m):
    return f"{m['name']}{m['descriptor']}"


def describe(surface, json_out):
    if json_out:
        print(json.dumps(surface, indent=2, sort_keys=True))
        return
    print(f"class {surface['this_class']}")
    print(f"  flags: {' '.join(surface['flags'])} (0x{surface['flag_bits']:04x})")
    print(f"  super: {surface['super_class']}  interfaces: {surface['interfaces'] or '[]'}")
    print(f"  classfile major: {surface['major']}")
    print(f"  fields: {len(surface['fields'])}  methods: {len(surface['methods'])}"
          f"  <clinit>: {surface['has_clinit']}")
    for kind, plural in (("field", "fields"), ("method", "methods")):
        for m in surface[plural]:
            extra = ""
            if "ConstantValue" in m["attributes"]:
                extra = f"  = {m['attributes']['ConstantValue']}"
            print(f"    {kind:6} {' '.join(m['flags']):40s} {member_key(m)}{extra}")


def compare_with_registry(surface, registry_path, class_dotted):
    registry = json.loads(registry_path.read_text())
    entry = next((e for e in registry["classes"] if e["class"] == class_dotted.replace(".", "/")), None)
    if entry is None:
        raise SystemExit(f"class {class_dotted} is not tracked in {registry_path}")
    declared = entry["surface"]
    problems = []
    if declared["methods_declared"] != len(surface["methods"]):
        problems.append(f"methods_declared {declared['methods_declared']} != classfile {len(surface['methods'])}")
    if declared["fields_declared"] != len(surface["fields"]):
        problems.append(f"fields_declared {declared['fields_declared']} != classfile {len(surface['fields'])}")
    for plural in ("methods", "fields"):
        without = declared.get(f"{plural}_without_evidence") or []
        real = {member_key(m) for m in surface[plural]}
        missing = [w for w in without if w not in real]
        if missing:
            problems.append(f"{plural}_without_evidence lists members the classfile does not declare: {missing}")
    real_methods = {member_key(m) for m in surface["methods"]}
    covered = declared["methods_with_evidence"]
    if covered > len(surface["methods"]):
        problems.append(f"methods_with_evidence {covered} > classfile methods {len(surface['methods'])}")
    if problems:
        print("MISMATCH between classfile and registry:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: registry matches classfile — {len(surface['methods'])} methods "
          f"({covered} with evidence), {len(surface['fields'])} fields, "
          f"<init>={surface['has_init']} <clinit>={surface['has_clinit']}")
    return {"methods": sorted(real_methods),
            "fields": sorted(member_key(m) for m in surface["fields"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("class_name", help="dotted name, e.g. net.minecraft.core.QuartPos")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--registry", type=pathlib.Path)
    ap.add_argument("--manifest", type=pathlib.Path,
                    help="write a deterministic evidence manifest (member list + hashes)")
    args = ap.parse_args()

    if not JAR.is_file():
        print(f"ERROR: {JAR} not found; run the README download steps", file=sys.stderr)
        return 2
    entry_path = args.class_name.replace(".", "/") + ".class"
    with zipfile.ZipFile(JAR) as z:
        try:
            data = z.read(entry_path)
        except KeyError:
            print(f"ERROR: {entry_path} not in {JAR.name}", file=sys.stderr)
            return 1
    surface = parse_class(data)
    describe(surface, args.json or bool(args.manifest))
    if args.registry:
        compare_with_registry(surface, args.registry, args.class_name)
    if args.manifest:
        manifest = {
            "schema": "classfile-surface-v1",
            "jar_sha256": hashlib.sha256(JAR.read_bytes()).hexdigest(),
            "class": surface["this_class"],
            "class_sha256": hashlib.sha256(data).hexdigest(),
            "flags": surface["flags"],
            "super_class": surface["super_class"],
            "interfaces": surface["interfaces"],
            "has_init": surface["has_init"],
            "has_clinit": surface["has_clinit"],
            "fields": [{"name": m["name"], "descriptor": m["descriptor"], "flags": m["flags"]}
                       for m in surface["fields"]],
            "methods": [{"name": m["name"], "descriptor": m["descriptor"], "flags": m["flags"]}
                        for m in surface["methods"]],
        }
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
