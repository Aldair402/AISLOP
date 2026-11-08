#!/usr/bin/env python3
"""TickThrottler: superficie reconciliada y comportamiento diferencial en nativo.

Clase candidata de A-02 fase 3 (ya ejecutada entera en `check-vanilla-first-class.py`,
120 guiones). Esta es la medición por miembro exigible para el registro:

1. **Superficie**: el classfile leído con el parser propio (`classfile-surface.py`,
   sin JDK) contra la reflexión de Java 25 del mismo JAR. Flags, superclase,
   interfaces, campos, métodos, constructor y modificadores de cada miembro.

2. **Diferencial por miembro** contra el binario nativo, sin JVM. La clase no expone
   accesor ni `toString`: lo único observable desde fuera es `isUnderThreshold()Z`, así
   que la evidencia de **todos** los miembros fluye por ahí y se declara en
   `cross_dependencies`:
   - `<init>(II)V` — se construyen instancias con pares (incrementStep, threshold)
     de un conjunto con límites (±0, ±1, ±1000, |i32| extremos) y se comprueba
     identidad de clase y que dos construcciones con los mismos argumentos son
     objetos distintos.
   - `increment()V` — tras `k` incrementos, `isUnderThreshold()Z` frente a Java 25.
     Incluye desbordamiento de `iadd` (paso 2³¹−1 con 2+ incrementos envuelve a
     negativo): distingue i32 con wrap de aritmética de palabra ancha.
   - `tick()V` — tras `k` incrementos y `m` ticks (incluido `m > k` y `m == k`),
     `isUnderThreshold()Z`. Con `count <= 0` el `ifle` del bytecode no decrementa:
     cubierto con pasos negativos/cero.
   - `isUnderThreshold()Z` — umbrales ≤ 0 (siempre cierto), `count == threshold`
     (falso por `if_icmpge`), `count < threshold` (cierto) y por encima (falso).
   - campos `incrementStep`, `threshold`, `count` — se ejercitan en **cada** caso
     anterior; no hay canal alternativo sin inventar accesor. Declarado, no escondido.

3. **Que no es un stub**: el Rust generado tiene que contener el layout de la clase
   y el despacho numérico de `isUnderThreshold()Z`. Un resultado correcto puede venir
   de un camino nativo equivocado; esto obliga a que exista el camino.

No certifica la clase. Con `--emit` escribe la clasificación medida en JSON para que
`update-class-evidence.py` la convierta en manifiesto e informe; quien firma es otro
frente.

Usage: python3 mc-aot/tests/check-tickthrottler-class-surface.py [--emit FILE]
"""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
JDK = pathlib.Path(os.environ.get("JAVA_HOME", "")) / "bin"
JAR = PROJECT / "downloads/server-26.3-inner.jar"
CLASS = "net/minecraft/util/TickThrottler"
CLASS_DOTTED = CLASS.replace("/", ".")
CLASSFILE_TOOL = ROOT / "tools/classfile-surface.py"
FIXTURE = "net/minecraft/test/TickThrottlerFixture"

# Conjuntos con límites: pasos, umbrales y pasos para el borde de isUnderThreshold.
STEP = [-2147483648, -1000000, -2, -1, 0, 1, 2, 7, 1000, 2147483647]
THR = [-2147483648, -1, 0, 1, 2, 3, 10, 1000]
THR2 = [-2147483648, -1, 0, 1, 2, 3, 5, 1000]

CASES_CONSTRUCTOR = range(0, 80)          # 10 pasos × 8 umbrales
CASES_INCREMENT = range(0, 720)           # 10 pasos × 8 umbrales × 9 repeticiones (1..9)
CASES_TICK = range(0, 720)                # idem, con ticks distintos por caso
CASES_THRESHOLD = range(0, 160)           # 8 umbrales × 10 extra (0..9)
TOTAL_RESULTS = len(CASES_CONSTRUCTOR) + len(CASES_INCREMENT) + len(CASES_TICK) + len(CASES_THRESHOLD)

REFLECT = """import net.minecraft.util.TickThrottler;
import java.lang.reflect.*;
import java.util.*;

public class TickThrottlerReflect {
    static String mods(int m) {
        List<String> out = new ArrayList<>();
        if ((m & Modifier.PUBLIC) != 0) out.add("public");
        if ((m & Modifier.PRIVATE) != 0) out.add("private");
        if ((m & Modifier.PROTECTED) != 0) out.add("protected");
        if ((m & Modifier.STATIC) != 0) out.add("static");
        if ((m & Modifier.FINAL) != 0) out.add("final");
        return String.join(" ", out);
    }
    static String type(Class<?> c) {
        if (c == int.class) return "I";
        if (c == void.class) return "V";
        if (c == boolean.class) return "Z";
        return "L" + c.getName().replace('.', '/') + ";";
    }
    static String descriptor(Executable e) {
        StringBuilder sb = new StringBuilder("(");
        for (Class<?> p : e.getParameterTypes()) sb.append(type(p));
        sb.append(")").append(e instanceof Method ? type(((Method) e).getReturnType()) : "V");
        return sb.toString();
    }
    public static void main(String[] a) {
        Class<?> k = TickThrottler.class;
        System.out.println("class_mods=" + mods(k.getModifiers()));
        System.out.println("class_final=" + Modifier.isFinal(k.getModifiers()));
        System.out.println("super=" + (k.getSuperclass() == null ? "null" : k.getSuperclass().getName().replace('.', '/')));
        System.out.println("interfaces=" + k.getInterfaces().length);
        for (Field f : k.getDeclaredFields())
            System.out.println("field=" + f.getName() + ":" + type(f.getType()) + ":" + mods(f.getModifiers()));
        for (Method m : k.getDeclaredMethods())
            System.out.println("method=" + m.getName() + ":" + descriptor(m) + ":" + mods(m.getModifiers()));
        for (Constructor<?> c : k.getDeclaredConstructors())
            System.out.println("ctor=" + descriptor(c) + ":" + mods(c.getModifiers()) + ":params=" + c.getParameterCount());
        // Comportamiento observable que el nativo debe reproducir con las mismas entradas.
        int[][] pairs = { {1, 3}, {0, 0}, {-1, -7} };
        for (int[] p : pairs) {
            TickThrottler t = new TickThrottler(p[0], p[1]);
            System.out.println("distinct=" + (t != new TickThrottler(p[0], p[1])));
            System.out.println("class=" + t.getClass().getName());
        }
    }
}
"""

FIXTURE_SOURCE = r"""package net.minecraft.test;
import net.minecraft.util.TickThrottler;

public class TickThrottlerFixture {
 static final int[] STEP = { __STEP__ };
 static final int[] THR = { __THR__ };
 static final int[] THR2 = { __THR2__ };

 static int constructor(int c) {
  int step = STEP[c % 10];
  int thr = THR[(c / 10) % 8];
  TickThrottler u = new TickThrottler(step, thr);
  TickThrottler v = new TickThrottler(step, thr);
  int score = 0;
  if (u != null) score += 1;
  if (u.getClass() == TickThrottler.class) score += 2;
  if (u != v) score += 4;
  if (v.getClass() == TickThrottler.class) score += 8;
  return score;
 }

 // op 1: increment()V — k incrementos, lectura por isUnderThreshold()Z
 static int incrementOp(int c) {
  int step = STEP[c % 10];
  int thr = THR[(c / 10) % 8];
  int reps = 1 + (c / 80);
  TickThrottler t = new TickThrottler(step, thr);
  for (int i = 0; i < reps; i++) t.increment();
  return t.isUnderThreshold() ? 1 : 0;
 }

 // op 2: tick()V — k incrementos y m ticks, lectura por isUnderThreshold()Z
 static int tickOp(int c) {
  int step = STEP[c % 10];
  int thr = THR[(c / 10) % 8];
  int reps = 1 + (c / 80);
  int ticks = (c * 7 + 3) % 11;
  TickThrottler t = new TickThrottler(step, thr);
  for (int i = 0; i < reps; i++) t.increment();
  for (int i = 0; i < ticks; i++) t.tick();
  return t.isUnderThreshold() ? 1 : 0;
 }

 // op 3: isUnderThreshold()Z — umbrales ≤ 0, igualdad count == threshold y lados
 static int thresholdOp(int c) {
  int thr = THR2[(c / 10) % 8];
  int extra = c % 10;
  TickThrottler t = new TickThrottler(1, thr);
  for (int i = 0; i < extra; i++) t.increment();
  return t.isUnderThreshold() ? 1 : 0;
 }

 public static int run(int n) {
  int op = n / 1000;
  int c = n % 1000;
  if (op == 0) return constructor(c);
  if (op == 1) return incrementOp(c);
  if (op == 2) return tickOp(c);
  return thresholdOp(c);
 }
}
"""

DRIVER = """import net.minecraft.test.TickThrottlerFixture;
public class TickThrottlerDriver {
 public static void main(String[] a) {
  for (int i = 0; i < a.length; i++) System.out.println(TickThrottlerFixture.run(Integer.parseInt(a[i])));
 }
}
"""

OPS = [("constructor", "<init>(II)V"),
       ("increment", "increment()V"),
       ("tick", "tick()V"),
       ("isUnderThreshold", "isUnderThreshold()Z")]
FIELD_MEMBERS = ["incrementStep:I", "threshold:I", "count:I"]


def fail(message):
    print(f"FALLO: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd, **kw):
    out = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if out.returncode:
        fail(f"{cmd[0]} falló: {out.stdout[-800:]}{out.stderr[-800:]}")
    return out


def classfile_surface():
    out = run([sys.executable, str(CLASSFILE_TOOL), CLASS_DOTTED, "--json"])
    return json.loads(out.stdout)


def reflection(directory):
    source = directory / "TickThrottlerReflect.java"
    source.write_text(REFLECT)
    run([str(JDK / "javac"), "-cp", str(JAR), "-d", str(directory), str(source)])
    out = run([str(JDK / "java"), "-cp", f"{directory}{os.pathsep}{JAR}", "TickThrottlerReflect"])
    parsed = {"fields": {}, "methods": {}, "ctors": []}
    for line in out.stdout.splitlines():
        if line.startswith("field="):
            name, desc, mods = line[6:].split(":", 2)
            parsed["fields"][f"{name}:{desc}"] = mods
        elif line.startswith("method="):
            name, desc, mods = line[7:].split(":", 2)
            parsed["methods"][f"{name}:{desc}"] = mods
        elif line.startswith("ctor="):
            desc, mods, params = line[5:].split(":", 2)
            parsed["ctors"].append({"descriptor": desc, "modifiers": mods, "params": params})
        elif "=" in line:
            key, value = line.split("=", 1)
            parsed.setdefault(key, []).append(value)
    return parsed


def reconcile(surface, reflect):
    problems = []
    if "final" in surface["flags"]:
        problems.append("el classfile marca la clase final y la reflexión debería coincidir")
    if reflect.get("class_final") != ["false"]:
        problems.append(f"la reflexión ve final={reflect.get('class_final')}")
    if surface["super_class"] != reflect.get("super", [None])[0]:
        problems.append(f"superclase distinta: classfile={surface['super_class']} reflejo={reflect.get('super')}")
    if len(surface["interfaces"]) != int(reflect.get("interfaces", ["-1"])[0]):
        problems.append(f"interfaces distintas: {surface['interfaces']} vs {reflect.get('interfaces')}")

    classfile_fields = {f"{m['name']}:{m['descriptor']}" for m in surface["fields"]}
    if classfile_fields != set(reflect["fields"]):
        problems.append(f"campos distintos: classfile={sorted(classfile_fields)} reflejo={sorted(reflect['fields'])}")

    classfile_methods = {f"{m['name']}:{m['descriptor']}" for m in surface["methods"] if m["name"] != "<init>"}
    if classfile_methods != set(reflect["methods"]):
        problems.append(f"métodos distintos: classfile={sorted(classfile_methods)} reflejo={sorted(reflect['methods'])}")

    EXPECTED_FLAGS = {"incrementStep:I": "private final", "threshold:I": "private final", "count:I": "private"}
    for member in surface["fields"] + surface["methods"]:
        key = f"{member['name']}:{member['descriptor']}"
        table = reflect["fields"] if member["kind"] == "field" else reflect["methods"]
        if key in table:
            parsed = {f for f in member["flags"] if f in ("public", "private", "protected", "static", "final")}
            seen = set(table[key].split()) if table[key] else set()
            if parsed != seen:
                problems.append(f"flags de {key}: classfile={sorted(parsed)} reflejo={sorted(seen)}")

    for key, expected in EXPECTED_FLAGS.items():
        if set(reflect["fields"].get(key, "").split()) != set(expected.split()):
            problems.append(f"modificadores de campo inesperados en {key}: {reflect['fields'].get(key)!r}")

    if not surface["has_init"]:
        problems.append("el classfile no declara <init>")
    if surface["has_clinit"]:
        problems.append("el classfile declara <clinit>: la medición asume que no hay estáticos")
    if len(reflect["ctors"]) != 1:
        problems.append(f"se esperaba un constructor, hay {len(reflect['ctors'])}")
    for ctor in reflect["ctors"]:
        if ctor["descriptor"] != "(II)V":
            problems.append(f"constructor inesperado {ctor['descriptor']}")
        if ctor["modifiers"] != "public":
            problems.append(f"el constructor debería ser public, es '{ctor['modifiers']}'")
        if ctor["params"] != "params=2":
            problems.append(f"el constructor debería tener dos parámetros: {ctor['params']}")

    distinct = reflect.get("distinct", [])
    if distinct != ["true", "true", "true"]:
        problems.append(f"dos construcciones con los mismos argumentos deberían ser objetos distintos: {distinct}")
    classes = set(reflect.get("class", []))
    if classes != {CLASS_DOTTED}:
        problems.append(f"getClass() inesperado: {classes}")
    if problems:
        for problem in problems:
            print(f"FALLO: {problem}", file=sys.stderr)
        raise SystemExit(1)


def table_literal(values):
    return ", ".join(str(v) for v in values)


def build_fixture(directory):
    """Compila el fixture contra la clase real y arma un JAR con el bytecode oficial."""
    src = directory / "src" / "net/minecraft/test/TickThrottlerFixture.java"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(FIXTURE_SOURCE.replace("__STEP__", table_literal(STEP))
                                .replace("__THR__", table_literal(THR))
                                .replace("__THR2__", table_literal(THR2)))
    (directory / "src/TickThrottlerDriver.java").write_text(DRIVER)
    classes = directory / "classes"
    run([str(JDK / "javac"), "-cp", str(JAR), "-d", str(classes), str(src),
         str(directory / "src/TickThrottlerDriver.java")])
    with zipfile.ZipFile(JAR) as z:
        payload = z.read(CLASS + ".class")
    target = classes / (CLASS + ".class")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    jar = directory / "fixture.jar"
    run([str(JDK / "jar"), "cf", str(jar), "-C", str(classes), "net"])
    return jar, digest


def cases():
    values = list(CASES_CONSTRUCTOR) + [1000 + c for c in CASES_INCREMENT] + \
             [2000 + c for c in CASES_TICK] + [3000 + c for c in CASES_THRESHOLD]
    return values


def check_generated(native_dir):
    """El camino nativo tiene que existir: no basta con que el resultado coincida."""
    generated = native_dir.with_suffix(".rs")
    if not generated.is_file():
        fail(f"no se encontró el Rust generado en {generated}")
    code = generated.read_text()
    if CLASS not in code:
        fail("el Rust generado no menciona la clase")
    if not re.search(r'"' + re.escape(CLASS) + r'"=>numeric_\d+\(heap,id\)', code):
        fail("no hay despacho numérico para la clase en el Rust generado")
    return True


def differential(directory, jar):
    values = cases()
    args = [value for v in values for value in ("0", str(v))]
    native_dir = directory / "native"
    built = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "Cargo.toml"), "--",
         "multi-static-demo", str(jar), FIXTURE, str(native_dir), "run", "(I)I"],
        text=True, capture_output=True, timeout=300)
    if built.returncode:
        fail(f"el traductor rechazó el fixture: {built.stderr[-1500:]}")
    check_generated(native_dir)

    java = run([str(JDK / "java"), "-cp", f"{directory / 'classes'}{os.pathsep}{directory / 'fixture.jar'}",
                "TickThrottlerDriver", *[str(v) for v in values]])
    native = subprocess.run([str(native_dir), *args], text=True, capture_output=True, timeout=120)
    if native.returncode:
        fail(f"el binario nativo abortó: {native.stderr[-800:]}")
    if native.stdout != java.stdout:
        pairs = list(zip(java.stdout.splitlines(), native.stdout.splitlines()))
        first = next((i for i, (a, b) in enumerate(pairs) if a != b), None)
        if first is None:
            fail(f"salidas de distinta longitud: java={len(pairs)} nativo={len(native.stdout.splitlines())}")
        op, case = divmod(values[first], 1000)
        detail = f"op={OPS[op][0]} caso={case} step={STEP[case % 10] if op else 0} java={pairs[first][0]} nativo={pairs[first][1]}"
        fail(f"diferencial roto en el primer desacuerdo: {detail}")

    # Ninguna operación puede salir toda a cero: un diferencial de ceros no mide nada.
    lines = java.stdout.splitlines()
    op_blocks = [list(CASES_CONSTRUCTOR), list(CASES_INCREMENT), list(CASES_TICK), list(CASES_THRESHOLD)]
    per_op = {}
    offset = 0
    for (name, member), block in zip(OPS, op_blocks):
        chunk = lines[offset:offset + len(block)]
        offset += len(block)
        if not any(value != "0" for value in chunk):
            fail(f"la operación {name} produce un resultado nulo para todas las entradas: {chunk}")
        per_op[name] = chunk
    return per_op, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--emit", type=pathlib.Path, help="escribe la clasificación medida en JSON")
    args = ap.parse_args()

    if not JAR.is_file():
        print(f"ERROR: falta {JAR}; ver «Preparación tras clonar» del README", file=sys.stderr)
        return 2
    if not JDK.is_dir():
        print("ERROR: JAVA_HOME no apunta a un JDK con bin/", file=sys.stderr)
        return 2

    surface = classfile_surface()
    with tempfile.TemporaryDirectory(prefix="mc-tickthrottler-") as tmp:
        directory = pathlib.Path(tmp)
        jar, class_sha = build_fixture(directory)
        reflect = reflection(directory)
        reconcile(surface, reflect)
        per_op, lines = differential(directory, jar)

    declared = {f"{m['name']}{m['descriptor']}" for m in surface["methods"]} | \
               {f"{m['name']}:{m['descriptor']}" for m in surface["fields"]}
    covered = {member for _, member in OPS} | set(FIELD_MEMBERS)
    missing = sorted(declared - covered)
    invented = sorted(covered - declared)
    if missing or invented:
        fail(f"la clasificación no cubre la superficie: faltan={missing} sobran={invented}")

    op_counts = dict(zip((name for name, _ in OPS), (len(per_op[name]) for name, _ in OPS)))
    classification = {
        "class": CLASS,
        "class_sha256": class_sha,
        "jar_sha256": hashlib.sha256(JAR.read_bytes()).hexdigest(),
        "differential_members": [
            {"member": member, "operation": name, "cases": op_counts[name]}
            for name, member in OPS
        ] + [
            {"member": member, "operation": "a través de las cuatro anteriores", "cases": TOTAL_RESULTS}
            for member in FIELD_MEMBERS
        ],
        "java_only_members": [],
        "reflection_gap_members": [],
        "cross_dependencies": [
            "La clase no expone accesor ni toString: todo el efecto de <init>(II)V y de los campos "
            "incrementStep, threshold y count se observa a través de isUnderThreshold()Z. Si "
            "isUnderThreshold()Z tradujera mal, fallarían a la vez el constructor, increment, tick y "
            "los tres campos; decirlo es distinto de esconderlo.",
            "El desbordamiento se cubre con paso 2147483647 y -2147483648 y con pasos negativos: la suma "
            "envuelve en i32 y Java 25 hace lo mismo; una aritmética de palabra ancha divergiría.",
        ],
        "results": len(lines),
    }
    if args.emit:
        args.emit.write_text(json.dumps(classification, indent=2, ensure_ascii=False) + "\n")

    print(f"OK: {len(lines)} resultados diferenciales Java 25 / nativo sin JVM sobre {CLASS} — "
          f"{len(CASES_CONSTRUCTOR)} pares de constructor (límites de i32), {len(CASES_INCREMENT)} "
          f"secuencias de incremento, {len(CASES_TICK)} de incremento+tick (con m > k y count <= 0) y "
          f"{len(CASES_THRESHOLD)} umbrales de borde (≤ 0, count == threshold); "
          f"superficie reconciliada classfile↔reflexión ({len(surface['methods'])} métodos, "
          f"{len(surface['fields'])} campos, constructor público de dos parámetros, sin <clinit>); "
          f"el Rust generado contiene la clase y su despacho numérico; no certifica la clase")
    return 0


if __name__ == "__main__":
    sys.exit(main())
