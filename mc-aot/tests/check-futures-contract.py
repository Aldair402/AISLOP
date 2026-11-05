#!/usr/bin/env python3
"""Contrato B-01: comprueba que el documento/JSON no afirma mas de lo demostrado.

No ejecuta Java ni el backend nativo (eso lo hacen los diferenciales que el
propio contrato cita). Verifica, sobre el repositorio:

1. Que cada caso con diferencial cite un test existente que este en
   mc-aot/run-regressions.sh (o, si es una prueba Rust de mc-aot/tests/*.rs,
   que el archivo exista: esas las ejecuta cargo test).
2. Que cada guarda citada exista literalmente en mc-aot/src.
3. Que cada prueba unitaria citada exista literalmente en mc-aot/src.
4. Que los oraculos Java existan, esten en la suite y que cada linea que el
   contrato dice que observan aparezca en el .java y en su runner.
5. Que cada evidencia en analysis/ exista.
6. Que toda tarea responsable exista en TODO.md.
7. Que el .md y el .json no se hayan desincronizado.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "analysis/futures-contract-b01.json"
DOC = ROOT / "analysis/futures-contract-b01.md"
SUITE = ROOT / "mc-aot/run-regressions.sh"
TODO = ROOT / "TODO.md"
SRC = ROOT / "mc-aot/src"

errors = []
summary = []


def fail(msg):
    errors.append(msg)


def text_of(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        fail(f"no se pudo leer {path.relative_to(ROOT)}")
        return ""


def rel(path):
    return str(path.relative_to(ROOT))


if not CONTRACT.exists():
    print(f"FALLO: no existe {rel(CONTRACT)}", file=sys.stderr)
    raise SystemExit(1)

data = json.loads(CONTRACT.read_text(encoding="utf-8"))
suite_text = text_of(SUITE)
todo_text = text_of(TODO)
doc_text = text_of(DOC) if DOC.exists() else ""

src_text = "\n".join(
    text_of(p) for p in sorted(SRC.rglob("*")) if p.is_file() and p.suffix in {".rs", ".inc"}
)
# Las pruebas unitarias del frente B viven también en mc-aot/tests/*.rs, que
# incluyen los módulos del runtime con el adaptador Rayon real.
src_text += "\n" + "\n".join(
    text_of(p) for p in sorted((ROOT / "mc-aot/tests").glob("*.rs"))
)

suite_tests = set(re.findall(r"mc-aot/tests/([A-Za-z0-9._-]+)\.py", suite_text))
declared_statuses = set(data.get("statuses", {}))

# ---------------------------------------------------------------- estructura
for field in ("contract", "title", "version", "updated", "base_commit", "scope", "oracles", "cases", "gaps"):
    if not data.get(field):
        fail(f"campo obligatorio ausente o vacio en el contrato: {field}")
if data.get("contract") != "B-01":
    fail("el contrato debe declararse B-01")
if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("updated", ""))):
    fail("updated debe ser YYYY-MM-DD")

# -------------------------------------------------------------------- tareas
todo_tasks = set(re.findall(r"\*\*([A-D]-\d{2}) ·", todo_text))
if not todo_tasks:
    fail("no se pudieron extraer IDs de tarea de TODO.md")


def check_owner(owner, where):
    if not owner:
        fail(f"{where}: falta responsable")
    elif owner not in todo_tasks:
        fail(f"{where}: responsable {owner} no existe en TODO.md")


# ------------------------------------------------------------------ oraculos
oracle_ids = {}
for oracle in data.get("oracles", []):
    oid = oracle.get("id")
    if not oid:
        fail("oraculo sin id")
        continue
    if oid in oracle_ids:
        fail(f"oraculo duplicado: {oid}")
    oracle_ids[oid] = oracle
    for key in ("java", "runner"):
        path = ROOT / str(oracle.get(key, ""))
        if not path.exists():
            fail(f"oraculo {oid}: no existe {oracle.get(key)}")
    java_text = text_of(ROOT / oracle["java"]) if (ROOT / oracle["java"]).exists() else ""
    runner_text = text_of(ROOT / oracle["runner"]) if (ROOT / oracle["runner"]).exists() else ""
    runner_name = pathlib.Path(oracle["runner"]).stem
    if runner_name not in suite_tests:
        fail(f"oraculo {oid}: {runner_name} no esta en mc-aot/run-regressions.sh")
    log = oracle.get("log")
    if not log:
        fail(f"oraculo {oid}: sin evidencia en analysis/")
    elif not (ROOT / log).exists():
        fail(f"oraculo {oid}: no existe la evidencia {log}")
    observes = oracle.get("observes") or []
    if not observes:
        fail(f"oraculo {oid}: no declara lineas observadas")
    for token in observes:
        if token not in java_text:
            fail(f"oraculo {oid}: '{token}' no aparece en {oracle['java']}")
        if runner_text and token not in runner_text:
            fail(f"oraculo {oid}: '{token}' no aparece en {oracle['runner']}")

# --------------------------------------------------------------------- casos
case_ids = []
seen = set()
for case in data.get("cases", []):
    cid = case.get("id", "<sin id>")
    where = f"caso {cid}"
    if cid in seen:
        fail(f"{where}: id duplicado")
    seen.add(cid)
    case_ids.append(cid)
    status = case.get("status")
    if status not in declared_statuses:
        fail(f"{where}: estado '{status}' no declarado en statuses")
    if not case.get("operation"):
        fail(f"{where}: falta operation")
    if not case.get("java_semantics"):
        fail(f"{where}: falta java_semantics")
    check_owner(case.get("owner"), where)

    for oracle_id in case.get("oracles") or []:
        if oracle_id not in oracle_ids:
            fail(f"{where}: oraculo desconocido {oracle_id}")

    for test in case.get("tests") or []:
        path = ROOT / test
        if not path.exists():
            fail(f"{where}: no existe el test {test}")
        elif path.suffix == ".py" and path.stem not in suite_tests:
            fail(f"{where}: {path.stem} no esta en mc-aot/run-regressions.sh")
        elif path.suffix == ".rs" and "tests/" not in test:
            fail(f"{where}: {test} no es una prueba de integracion de mc-aot/tests")

    for log in case.get("logs") or []:
        if not (ROOT / log).exists():
            fail(f"{where}: no existe la evidencia {log}")

    if status == "differential":
        if not case.get("tests"):
            fail(f"{where}: se declara diferencial sin ningun test")
        if case.get("unit_test"):
            fail(f"{where}: un diferencial no puede apoyarse solo en prueba unitaria")
    elif status == "guard":
        message = case.get("guard_message")
        if not message:
            fail(f"{where}: guarda sin mensaje literal")
        elif message not in src_text:
            fail(f"{where}: el mensaje '{message}' no existe en mc-aot/src")
    elif status == "unit":
        name = case.get("unit_test")
        if not name:
            fail(f"{where}: prueba unitaria sin nombre")
        elif name not in src_text:
            fail(f"{where}: la prueba '{name}' no existe en mc-aot/src")
        if not case.get("src") or not (ROOT / case["src"]).exists():
            fail(f"{where}: falta el archivo de origen de la prueba unitaria")
    elif status == "java-only":
        if not case.get("oracles"):
            fail(f"{where}: se declara solo-Java sin oraculo que lo fije")
    elif status == "unsupported":
        if not (case.get("note") or "").strip():
            fail(f"{where}: un caso no soportado debe explicar que falta")

    # una guarda declarada debe existir aunque el estado no sea 'guard'
    if case.get("guard_message") and status != "guard" and case["guard_message"] not in src_text:
        fail(f"{where}: el mensaje '{case['guard_message']}' no existe en mc-aot/src")

    summary.append((cid, case.get("operation", ""), status, case.get("owner", "")))

# ---------------------------------------------------------------- huecos
for gap in data.get("gaps", []):
    gid = gap.get("id", "<sin id>")
    if not str(gid).startswith("gap."):
        fail(f"hueco {gid}: el id debe empezar por 'gap.'")
    for field in ("description", "action"):
        if not gap.get(field):
            fail(f"hueco {gid}: falta {field}")
    check_owner(gap.get("owner"), f"hueco {gid}")

# ------------------------------------------------------------- doc sincronizado
if not doc_text:
    fail(f"no existe o esta vacio {rel(DOC)}")
else:
    for cid in case_ids:
        if cid not in doc_text:
            fail(f"el documento no menciona el caso {cid}")
    for gap in data.get("gaps", []):
        if gap.get("id") and gap["id"] not in doc_text:
            fail(f"el documento no menciona el hueco {gap['id']}")
    prefixes = sorted({cid.split(".")[0] for cid in case_ids} | {"gap"})
    known = set(case_ids) | {gap.get("id") for gap in data.get("gaps", [])}
    pattern = re.compile(
        r"(?<![\w.-])(" + "|".join(map(re.escape, prefixes)) + r")\.[a-z0-9]+(?:-[a-z0-9]+)*"
    )
    for token in {m.group(0) for m in pattern.finditer(doc_text)}:
        if token not in known:
            fail(f"el documento cita {token}, que no existe en el contrato")

# ------------------------------------------------------------------- resumen
if "--summary" in sys.argv:
    for cid, operation, status, owner in summary:
        print(f"{cid:38s} {operation:18s} {status:13s} {owner}")

counts = {}
for _, _, status, _ in summary:
    counts[status] = counts.get(status, 0) + 1
print(
    "Resumen B-01: "
    + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    + f"; oraculos={len(oracle_ids)}; huecos={len(data.get('gaps', []))}"
)

if errors:
    for error in errors:
        print(f"FALLO: {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "OK: contrato B-01 coherente con el repositorio: cada diferencial cita un test que esta en la suite, "
    "cada guarda existe literalmente en mc-aot/src, cada prueba unitaria existe, cada oraculo Java esta "
    "en la suite y sus lineas observadas coinciden con su codigo y su runner, y el documento y el JSON no divergen. "
    "NO verifica semantica ni equivalencia con Java: eso solo lo demuestran los diferenciales citados."
)
