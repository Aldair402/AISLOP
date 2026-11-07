#!/usr/bin/env python3
"""El contrato A-01 se comprueba contra el código, no contra la prosa.

`analysis/a01-contrato-integracion.md` decide la frontera entre el backend numérico
(frente A) y el concurrente (frente B). Un contrato que solo vive en un markdown se
queda viejo el día que alguien renombra una función o suaviza un mensaje de rechazo.
Esta etapa lee el documento, verifica cada afirmación comprobable y falla cuando el
documento y el código dejan de decir lo mismo — en cualquiera de las dos direcciones.

Comprueba:
  1. literales de rechazo citados en el contrato  -> existen en mc-aot/src
  2. funciones nombradas                          -> existen en el archivo declarado
  3. reglas de locks (D7/D8)                      -> patrón prohibido ausente, drop antes de delegar
  4. pruebas citadas                              -> existen por nombre y están en la suite
  5. D12 (opt-in)                                 -> describe la divergencia real, no una inventada
  6. no certifica                                 -> count_complete sigue en 0

No comprueba: que el orden de locks sea correcto en todas las rutas, ni el modelo de
memoria JVM. Un `grep` no prueba ausencia de interbloqueos; eso lo dicen las pruebas
con timeout.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
CONTRACT = PROJECT / "analysis/a01-contrato-integracion.md"

SRC = {
    "executor": ROOT / "src/executor_runtime.rs",
    "heap": ROOT / "src/concurrent_heap.rs",
    "runtime": ROOT / "src/numeric_runtime.inc",
    "graph": ROOT / "src/numeric_concurrent_graph_bridge.inc",
    "numeric": ROOT / "src/numeric.rs",
    "concurrent_compile": ROOT / "src/concurrent_compile.rs",
}

# 1. Literales que el contrato presenta como rechazos declarados.
LITERALS = [
    "grafo: otro heap numérico",
    "grafo: identidad inconsistente",
    "grafo: destino no registrado o incompatible",
    "grafo: tipo de campo incompatible",
    "publicación: sesión ya instalada",
    "publicación: sesión ya activa para este heap",
    "publicación: hilo distinto al de la sesión",
    "captura de referencia debe ser final",
    "pool cerrado",
    "awaitTermination desde worker propio no soportado",
    "cancel de futuro pendiente no soportado",
]

# 2. Símbolos que el contrato nombra, con el archivo que declara cada uno.
SYMBOLS = [
    ("executor", r"pub fn create\("),
    ("executor", r"pub fn join\("),
    ("executor", r"pub fn await_termination\("),
    ("executor", r"pub fn shutdown\("),
    ("executor", r"pub fn is_terminated\("),
    ("executor", r"pub fn parallelism\("),
    ("heap", r"pub fn read\("),
    ("heap", r"pub fn write\("),
    ("heap", r"pub fn enter\("),
    ("heap", r"pub fn mark_pending_future\("),
    ("heap", r"pub fn future_complete\("),
    ("runtime", r"fn install_publish_session\("),
    ("runtime", r"fn publish_active_insert\("),
    ("runtime", r"fn publish_active_owner_of\("),
    ("runtime", r"struct PublishSessionGuard"),
    ("numeric", r"fn futures_optin\("),
]

# 4. Pruebas citadas por el contrato.
RUST_TESTS = ["pending_future_published_to_a_worker_is_visible",
              "foreign_heap_references_are_rejected",
              "await_termination_is_callers_only",
              "close_is_idempotent_and_final",
              "submit_and_join_are_idempotent_and_scoped",
              "create_accepts_only_the_declared_parallelism"]
PY_TESTS = ["check-numeric-concurrent-graph.py",
            "check-numeric-auto-publish.py",
            "check-numeric-mutable-refs.py",
            "check-futures-contract.py",
            "check-rayon-pending-future.py"]

problems = []


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main():
    contract = read(CONTRACT)
    if not contract:
        print(f"FALLO: falta {CONTRACT.relative_to(PROJECT)}", file=sys.stderr)
        return 2
    sources = {name: read(path) for name, path in SRC.items()}

    # --- las doce decisiones tienen que estar escritas ---
    for n in range(1, 13):
        if f"| D{n} |" not in contract:
            problems.append(f"el contrato no contiene la decisión D{n}")

    # 1. literales
    for literal in LITERALS:
        hits = [name for name, text in sources.items() if literal in text]
        if not hits:
            problems.append(f"el contrato cita un rechazo que no existe en mc-aot/src: '{literal}'")
        elif f'"{literal}"' not in contract and literal not in contract:
            problems.append(f"el literal '{literal}' existe pero el contrato no lo cita")

    # 2. símbolos
    for name, pattern in SYMBOLS:
        if not re.search(pattern, sources[name]):
            problems.append(f"el contrato nombra `{pattern}` y no está en {SRC[name].name}")

    # 3. reglas de locks (D7/D8)
    graph = sources["graph"]
    for number, line in enumerate(graph.splitlines(), 1):
        if "fields.lock()" in line and "map.lock()" in line:
            problems.append(f"{SRC['graph'].name}:{number} toma el lock de campos y el del mapa a la vez (D7)")
    heap = sources["heap"]
    for function in ("read", "write", "enter"):
        body = re.search(rf"pub fn {function}\((.*?)\n    \}}", heap, re.S)
        if not body:
            problems.append(f"no se pudo leer el cuerpo de `{function}` para comprobar D7")
            continue
        text = body.group(1)
        if "external" in text and not re.search(r"drop\(store\)", text):
            problems.append(f"`{function}` delega en un objeto externo sin soltar el lock de la tabla (D7)")
    if "enum MonitorGuard" not in heap or "Local(" not in heap or "External" not in heap:
        problems.append("MonitorGuard no tiene las dos variantes que D8 describe")

    # 4. pruebas citadas
    rust = read(ROOT / "tests/rayon_b_api.rs")
    for name in RUST_TESTS:
        if f"fn {name}(" not in rust:
            problems.append(f"el contrato cita la prueba `{name}` y no está en rayon_b_api.rs")
    suite = read(ROOT / "run-regressions.sh")
    for name in PY_TESTS:
        if not (ROOT / "tests" / name).is_file():
            problems.append(f"el contrato cita `{name}` y el archivo no existe")
        elif f"tests/{name}" not in suite:
            problems.append(f"`{name}` existe pero no está registrada en run-regressions.sh")

    # 5. D12 describe la divergencia real (o su ausencia)
    a_only = re.findall(r'value == std::ffi::OsStr::new\("([^"]+)"\)', sources["numeric"])
    b_text = sources["concurrent_compile"]
    b_match = re.search(r"fn futures_\w*optin\(\)(.*?)\n\}", b_text, re.S)
    b_only = re.findall(r'\bv? ?== "([^"]+)"', b_match.group(1)) if b_match else []
    b_only = [v for v in b_only if v not in ("1",)]
    contract_says_divergence = "no comparten ningún valor" in contract
    if b_match:
        common = set(a_only) & set(b_only)
        if common and contract_says_divergence:
            problems.append(f"el contrato dice que no hay valor común y sí lo hay: {sorted(common)}")
        if not common and not contract_says_divergence:
            problems.append("los dos backends no comparten ningún valor y el contrato no lo dice")
    elif contract_says_divergence and not any(
            "b-01" in line and "no está integrada" in contract for line in contract.splitlines()):
        problems.append("el contrato habla de divergencia sin explicar que la mitad de B no está en main")

    # 6. nada certifica
    registry = json.loads(read(PROJECT / "analysis/class-registry.json"))
    if registry.get("count_complete") != 0:
        problems.append("el contrato no certifica clases y count_complete ya no es 0")
    if any(entry.get("certified") for entry in registry.get("classes", [])):
        problems.append("hay una clase certificada sin que el contrato lo refleje")

    if problems:
        for problem in problems:
            print(f"FALLO: {problem}", file=sys.stderr)
        return 1
    print(f"OK: contrato A-01 comprobado — 12 decisiones presentes, {len(LITERALS)} literales de rechazo "
          f"existen en mc-aot/src, {len(SYMBOLS)} símbolos en su archivo declarado, las reglas de locks D7/D8 "
          f"se cumplen en los archivos citados (sin lock de campos+mapa simultáneo y con drop antes de delegar), "
          f"{len(RUST_TESTS) + len(PY_TESTS)} pruebas citadas existen y están registradas, D12 describe la "
          f"divergencia de opt-in real y el contador sigue en 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
