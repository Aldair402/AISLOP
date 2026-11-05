#!/usr/bin/env python3
"""Validate class-registry.json: verifiable counter, no auto-counting."""
import hashlib, json, pathlib, re, sys, zipfile
root = pathlib.Path(__file__).resolve().parents[2]
reg_path = root / "analysis/class-registry.json"
jar_path = root / "downloads/server-26.3-inner.jar"

def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024*1024), b""):
            h.update(c)
    return h.hexdigest()

# The JAR is a third-party download (gitignored), so a fresh clone and CI may
# not have it. Without it we can still validate the registry schema, statuses,
# counts and evidence files, but class-level hashes stay unverified.
jar_present = jar_path.is_file()

def err(m): raise ValueError(m)

data = json.loads(reg_path.read_text())
if data.get("schema") != "class-registry-v1": err("schema must be class-registry-v1")
if not re.fullmatch(r"[0-9a-f]{64}", data.get("jar_sha256","")): err("jar_sha256 invalid")
if data["jar_classes_total"] != 7762: err("jar_classes_total must be 7762")
if not isinstance(data["count_complete"], int) or data["count_complete"] < 0: err("count_complete invalid")
jar_hashes = None
if jar_present:
    if sha(jar_path) != data["jar_sha256"]: err(f"JAR hash mismatch: expected {data['jar_sha256']} got {sha(jar_path)}")
    # Verify jar has 7762 classes
    with zipfile.ZipFile(jar_path) as z:
        names = [i.filename for i in z.infolist() if i.filename.endswith(".class")]
        if len(names) != 7762: err(f"JAR class count {len(names)} != 7762")
        jar_names = set(names)
        jar_hashes = {n: hashlib.sha256(z.read(n)).hexdigest() for n in names}
else:
    print("WARN: downloads/server-26.3-inner.jar not present — structural checks only, "
          "class hashes unverified (run README download steps to verify)", file=sys.stderr)

allowed_status = {"inventoried","partial-evidence","pending-review","complete"}
seen = set()
complete_entries = []
for entry in data.get("classes", []):
    for k in ("class","status","jar_sha256","class_sha256","surface","evidence","certified"):
        if k not in entry: err(f"missing {k} in {entry.get('class')}")
    cls = entry["class"]
    if not re.fullmatch(r"[A-Za-z0-9_/$]+", cls): err(f"invalid class name {cls}")
    if cls in seen: err(f"duplicate class {cls}")
    seen.add(cls)
    if entry["status"] not in allowed_status: err(f"invalid status {entry['status']}")
    if entry["jar_sha256"] != data["jar_sha256"]: err(f"class {cls} jar_sha256 mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", entry["class_sha256"]): err(f"invalid class_sha256 for {cls}")
    if jar_hashes is not None and jar_hashes.get(cls+".class") != entry["class_sha256"]: err(f"class hash mismatch for {cls}")
    surf = entry["surface"]
    for k in ("methods_declared","fields_declared","methods_with_evidence","fields_with_evidence"):
        if not isinstance(surf[k], int): err(f"surface int missing for {cls}")
    if surf["methods_with_evidence"] > surf["methods_declared"]: err(f"more evidence than declared for {cls}")
    # evidence files exist and hashes match
    for key in ("manifest","report"):
        p = entry["evidence"].get(key)
        if p:
            path = (root / p).resolve()
            if not path.is_file(): err(f"evidence missing {p}")
            if not path.is_relative_to(root.resolve()): err(f"evidence outside root {p}")
    # status vs certified
    if entry["status"] == "complete":
        if not entry["certified"]: err(f"complete must be certified {cls}")
        if not entry.get("review"): err(f"complete must have review {cls}")
        if surf["methods_without_evidence"] or surf["fields_without_evidence"]: err(f"complete cannot have gaps {cls}")
        complete_entries.append(cls)
    else:
        if entry["certified"] and entry["status"] != "pending-review":
            err(f"only pending-review or complete can be certified {cls}")
        if entry["status"] == "partial-evidence" and not entry.get("limitations"):
            err(f"partial-evidence must list limitations {cls}")
    if entry["status"] == "complete" and entry["review"] is None:
        err(f"complete review null {cls}")

# count must match
if data["count_complete"] != len(complete_entries):
    err(f"count_complete {data['count_complete']} != len(complete) {len(complete_entries)}")
# complete and pending_review arrays must match count logic
if data["count_complete"] != len(data.get("complete", [])):
    err("complete[] length must equal count_complete")
if data["count_complete"] != 0 and not complete_entries:
    err("non-zero count without complete entries")

# Verify evidence sha256 for QuartPos manifest files via existing tool
for entry in data["classes"]:
    manifest = entry["evidence"].get("manifest")
    if manifest and manifest == "analysis/class-evidence/quartpos.json":
        mdata = json.loads((root / manifest).read_text())
        for item in mdata.get("members", []):
            for ev in item.get("evidence", []):
                p = root / ev["path"]
                if sha(p) != ev["sha256"]:
                    err(f"manifest evidence hash mismatch {ev['path']}")

mode = "7762 classes verified against JAR" if jar_present else "JAR absent, hashes unverified"
print(f"OK: registry valid — {len(data['classes'])} tracked, count_complete={data['count_complete']} (0 until review), JAR {data['jar_sha256'][:8]}..., {mode}")
print(f"  statuses: {', '.join(e['class']+':'+e['status'] for e in data['classes'])}")
