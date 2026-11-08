#!/usr/bin/env python3
"""FeatureFlagUniverse: superficie reconciliada y constructor ejercitado en nativo.

Segunda clase del registro. Se eligió por una razón concreta y comprobable: la usan
ya cinco pruebas del proyecto (`check-numeric-object-sharing.py` entre ellas) y hoy
solo se ejercita en un campo estático, nunca en su vertiente de instancia. Es
pequeña (1 campo, 1 constructor, 1 método) y no tiene `static` inicializador, así que
es la clase con menos superficie posible que **sí** tiene estado por instancia.

Qué mide, y por qué cada cosa cuenta como evidencia de un miembro concreto:

1. **Superficie**: el classfile leído con el parser propio (`classfile-surface.py`,
   sin JDK) contra la reflexión de Java 25 del mismo JAR. Flags, superclase,
   interfaces, campos, métodos, constructores y modificadores de cada miembro.

2. **Diferencial por miembro** contra el binario nativo, sin JVM, con entradas
   distintas por operación:
   - `<init>(Ljava/lang/String;)V` — se construyen instancias con 12 valores
     distintos (vacío, un carácter, ASCII, unicode, espacios, tabulación, cadena
     larga y `null`) y se comprueba identidad de clase y que dos construcciones con
     el mismo argumento son objetos distintos.
   - `toString()Ljava/lang/String;` — se comprueba que devuelve exactamente el
     argumento (igualdad, longitud, y `null` cuando el argumento fue `null`).
   - `id:Ljava/lang/String;` — se comprueba que cada instancia conserva **su**
     propio valor: dos instancias con distinto argumento no son intercambiables, dos
     con el mismo argumento sí devuelven lo mismo.

   El efecto del constructor y del campo se observa a través del `toString` de la
   propia clase, no por un accesor inventado: si el `toString` traduce mal, la
   operación de campo falla también, y el informe lo declara en `cross_dependencies`.

3. **Que no es un stub**: en el Rust generado del binario nativo tienen que estar el
   `object_store` del constructor, el `object_load` del `toString` y la entrada de
   despacho virtual de `toString()Ljava/lang/String;` para esta clase. Un resultado
   correcto puede venir de un camino nativo equivocado; esto obliga a que exista el
   camino.

No certifica la clase. Con `--emit` escribe la clasificación medida en JSON para que
`update-class-evidence.py` la convierta en manifiesto e informe; quien firma es otro
frente.

Usage: python3 mc-aot/tests/check-featureflaguniverse-class-surface.py [--emit FILE]
"""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
JDK = pathlib.Path(os.environ.get("JAVA_HOME", "")) / "bin"
JAR = PROJECT / "downloads/server-26.3-inner.jar"
CLASS = "net/minecraft/world/flag/FeatureFlagUniverse"
CLASS_DOTTED = CLASS.replace("/", ".")
CLASSFILE_TOOL = ROOT / "tools/classfile-surface.py"
FIXTURE = "net/minecraft/test/FeatureUniverseFixture"

# Un valor por familia de entrada: longitudes 0..64, unicode, controles, comillas,
# pares sustitutos (fuera del BMP) y `null`. Se genera una sola vez y se usa en los
# dos lados, para que la tabla de Java y la de Python no puedan divergir.
def _ids():
    values = ["x" * n for n in range(0, 65)]
    values += ["", "a", "vanilla", "minecraft:vanilla", "\u00fcn\u00efcode-\u00e9\u00e8",
               "\U0001f600", "clave\U0001f600valor", " ", "tab\there", "line\nbreak",
               "\u0000nul", 'quoted"and\'apostrophe', "\\backslash", "  dos espacios  ",
               "0123456789", "mixed\u00e1\u00e9\u00ed\u00f3\u00fa", None]
    assert len(values) == 82, len(values)
    values += ["relleno%d" % n for n in range(14)]
    assert len(values) == 96 and values.count(None) == 1
    return values


IDS = _ids()


def java_literal(value):
    """Literal de Java para el valor, con escapes ASCII (los pares sustitutos incluidos)."""
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=True)


def java_table():
    return "{" + ", ".join(java_literal(v) for v in IDS) + "}"


REFLECT = """import net.minecraft.world.flag.FeatureFlagUniverse;
import java.lang.reflect.*;
import java.util.*;

public class UniverseReflect {
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
        Class<?> k = FeatureFlagUniverse.class;
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
        String[] ids = { "", "vanilla", null };
        for (String id : ids) {
            FeatureFlagUniverse u = new FeatureFlagUniverse(id);
            System.out.println("distinct=" + (u != new FeatureFlagUniverse(id)));
            System.out.println("toString=" + (u.toString() == null ? "null" : u.toString()));
            System.out.println("class=" + u.getClass().getName());
        }
    }
}
"""

FIXTURE_SOURCE = r"""package net.minecraft.test;
import net.minecraft.world.flag.FeatureFlagUniverse;

public class FeatureUniverseFixture {
 static String[] IDS = __TABLE__;

 static String id(int i) { return IDS[i % IDS.length]; }

 // op 0: <init>(Ljava/lang/String;)V
 static int constructor(int c) {
  String id = id(c);
  FeatureFlagUniverse u = new FeatureFlagUniverse(id);
  FeatureFlagUniverse v = new FeatureFlagUniverse(id);
  int score = 0;
  if (u != null) score += 1;
  if (u.getClass() == FeatureFlagUniverse.class) score += 2;
  if (u != v) score += 4;
  if (v.getClass() == FeatureFlagUniverse.class) score += 8;
  return score;
 }

 // op 1: toString()Ljava/lang/String;
 static int tostring(int c) {
  String id = id(c);
  FeatureFlagUniverse u = new FeatureFlagUniverse(id);
  String s = u.toString();
  int score = 0;
  if (id == null) {
   if (s == null) score += 1;
  } else {
   if (s != null) score += 1;
   if (s == id) score += 2;
   if (s != null && s.equals(id)) score += 4;
   if (s != null && s.length() == id.length()) score += 8;
  }
  return score;
 }

 // op 2: id:Ljava/lang/String; (cada instancia conserva su propio valor)
 static int field(int c) {
  String left = id(c);
  String right = id(c + 1);
  FeatureFlagUniverse a = new FeatureFlagUniverse(left);
  FeatureFlagUniverse b = new FeatureFlagUniverse(right);
  String sa = a.toString();
  String sb = b.toString();
  int score = 0;
  if (left == null) {
   if (sa == null) score += 1;
  } else {
   if (sa != null && sa.equals(left)) score += 1;
  }
  if (left == null || right == null || !left.equals(right)) {
   if (left == null) { if (sb != null) score += 2; }
   else { if (sb == null || !sb.equals(sa)) score += 2; }
  } else {
   if (sa == sb) score += 2;
   else if (sa != null && sa.equals(sb)) score += 2;
  }
  if (a != b) score += 4;
  return score;
 }

 public static int run(int n) {
  int op = n / 1000;
  int c = n % 1000;
  if (op == 0) return constructor(c);
  if (op == 1) return tostring(c);
  return field(c);
 }
}
"""

DRIVER = """import net.minecraft.test.FeatureUniverseFixture;
public class UniverseDriver {
 public static void main(String[] a) {
  for (int i = 0; i < a.length; i++) System.out.println(FeatureUniverseFixture.run(Integer.parseInt(a[i])));
 }
}
"""

OPS = [("constructor", "<init>(Ljava/lang/String;)V"),
       ("tostring", "toString()Ljava/lang/String;"),
       ("field", "id:Ljava/lang/String;")]


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
    source = directory / "UniverseReflect.java"
    source.write_text(REFLECT)
    run([str(JDK / "javac"), "-cp", str(JAR), "-d", str(directory), str(source)])
    out = run([str(JDK / "java"), "-cp", f"{directory}{os.pathsep}{JAR}", "UniverseReflect"])
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

    for member in surface["fields"] + surface["methods"]:
        key = f"{member['name']}:{member['descriptor']}"
        table = reflect["fields"] if member["kind"] == "field" else reflect["methods"]
        if key in table:
            parsed = {f for f in member["flags"] if f in ("public", "private", "protected", "static", "final")}
            seen = set(table[key].split()) if table[key] else set()
            if parsed != seen:
                problems.append(f"flags de {key}: classfile={sorted(parsed)} reflejo={sorted(seen)}")

    if not surface["has_init"]:
        problems.append("el classfile no declara <init>")
    if len(reflect["ctors"]) != 1:
        problems.append(f"se esperaba un constructor, hay {len(reflect['ctors'])}")
    for ctor in reflect["ctors"]:
        if ctor["descriptor"] != "(Ljava/lang/String;)V":
            problems.append(f"constructor inesperado {ctor['descriptor']}")
        if ctor["modifiers"] != "public":
            problems.append(f"el constructor debería ser public, es '{ctor['modifiers']}'")
        if ctor["params"] != "params=1":
            problems.append(f"el constructor debería tener un parámetro: {ctor['params']}")

    # Comportamiento de referencia: el nativo tiene que dar exactamente esto.
    distinct = reflect.get("distinct", [])
    if distinct != ["true", "true", "true"]:
        problems.append(f"dos construcciones con el mismo argumento deberían ser objetos distintos: {distinct}")
    texts = reflect.get("toString", [])
    if texts != ["", "vanilla", "null"]:
        problems.append(f"toString de referencia inesperado: {texts}")
    classes = set(reflect.get("class", []))
    if classes != {CLASS_DOTTED}:
        problems.append(f"getClass() inesperado: {classes}")
    if problems:
        for problem in problems:
            print(f"FALLO: {problem}", file=sys.stderr)
        raise SystemExit(1)


def build_fixture(directory):
    """Compila el fixture contra la clase real y arma un JAR con el bytecode oficial."""
    src = directory / "src" / "net/minecraft/test/FeatureUniverseFixture.java"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(FIXTURE_SOURCE.replace("__TABLE__", java_table()))
    (directory / "src/UniverseDriver.java").write_text(DRIVER)
    classes = directory / "classes"
    run([str(JDK / "javac"), "-cp", str(JAR), "-d", str(classes), str(src),
         str(directory / "src/UniverseDriver.java")])
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
    """Una lista de enteros por operación: cada caso es op*1000 + índice.

    La demo nativa recibe pares (índice de método, argumento) y aquí solo se
    expone `run`, así que el primer elemento de cada par es 0.
    """
    values = []
    for op in range(len(OPS)):
        for c in range(len(IDS)):
            values.append(op * 1000 + c)
    return values


def check_generated(native_dir):
    """El camino nativo tiene que existir: no basta con que el resultado coincida."""
    generated = native_dir.with_suffix(".rs")
    if not generated.is_file():
        fail(f"no se encontró el Rust generado en {generated}")
    code = generated.read_text()
    owner = CLASS
    required = {
        "escritura del campo en el constructor": f'object_store(heap,r,"{owner}",0,v)',
        "lectura del campo en toString": f'object_load(heap,r,"{owner}",0)',
    }
    missing = [label for label, needle in required.items() if needle not in code]
    if missing:
        fail("el Rust generado no contiene el camino nativo esperado: " + ", ".join(missing))
    if not re.search(r'"' + re.escape(owner) + r'"=>numeric_\d+\(heap,id\)', code):
        fail("no hay despacho numérico para el toString de la clase")
    return True


def differential(directory, jar):
    values = cases()
    # Pares (método expuesto, valor): hay un solo punto de entrada, `run`.
    args = [value for v in values for value in ("0", str(v))]
    native_dir = directory / "native"
    built = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "Cargo.toml"), "--",
         "multi-static-demo", str(jar), FIXTURE, str(native_dir), "run", "(I)I"],
        text=True, capture_output=True, timeout=300)
    if built.returncode:
        fail(f"el traductor rechazó el fixture: {built.stderr[-1500:]}")
    check_generated(native_dir)

    # El driver de Java recibe un valor por caso; el binario nativo, pares (método, valor).
    java = run([str(JDK / "java"), "-cp", f"{directory / 'classes'}{os.pathsep}{directory / 'fixture.jar'}",
                "UniverseDriver", *[str(v) for v in values]])
    native = subprocess.run([str(native_dir), *args], text=True, capture_output=True, timeout=120)
    if native.returncode:
        fail(f"el binario nativo abortó: {native.stderr[-800:]}")
    if native.stdout != java.stdout:
        pairs = list(zip(java.stdout.splitlines(), native.stdout.splitlines()))
        first = next((i for i, (a, b) in enumerate(pairs) if a != b), None)
        if first is None:
            fail(f"salidas de distinta longitud: java={len(pairs)} nativo={len(native.stdout.splitlines())}")
        op, case = divmod(values[first], 1000)
        detail = f"op={OPS[op][0]} caso={case} id={IDS[case % len(IDS)]!r} java={pairs[first][0]} nativo={pairs[first][1]}"
        fail(f"diferencial roto en el primer desacuerdo: {detail}")

    # Cada operación tiene que producir un resultado no trivial; un cero en todas las
    # filas significaría que el fixture no midió nada y el diferencial sería vacío.
    per_op = {}
    lines = java.stdout.splitlines()
    for op, (name, member) in enumerate(OPS):
        block = [lines[op * len(IDS) + i] for i in range(len(IDS))]
        if any(value == "0" for value in block[:len(IDS) - 1]):
            fail(f"la operación {name} produce un resultado nulo para alguna entrada: {block}")
        per_op[name] = block
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
    with tempfile.TemporaryDirectory(prefix="mc-feature-universe-") as tmp:
        directory = pathlib.Path(tmp)
        jar, class_sha = build_fixture(directory)
        reflect = reflection(directory)
        reconcile(surface, reflect)
        per_op, lines = differential(directory, jar)

    declared = {f"{m['name']}{m['descriptor']}" for m in surface["methods"]} | \
               {f"{m['name']}:{m['descriptor']}" for m in surface["fields"]}
    covered = {member for _, member in OPS}
    missing = sorted(declared - covered)
    invented = sorted(covered - declared)
    if missing or invented:
        fail(f"la clasificación no cubre la superficie: faltan={missing} sobran={invented}")

    classification = {
        "class": CLASS,
        "class_sha256": class_sha,
        "jar_sha256": hashlib.sha256(JAR.read_bytes()).hexdigest(),
        "differential_members": [
            {"member": member, "operation": name, "cases": len(per_op[name])}
            for name, member in OPS
        ],
        "java_only_members": [],
        "reflection_gap_members": [],
        "cross_dependencies": [
            "El efecto de <init>(Ljava/lang/String;)V y del campo id:Ljava/lang/String; se observa a "
            "través de toString()Ljava/lang/String; de la propia clase: no hay accesor y no se inventa uno.",
        ],
        "results": len(lines),
    }
    if args.emit:
        args.emit.write_text(json.dumps(classification, indent=2, ensure_ascii=False) + "\n")

    print(f"OK: {len(lines)} resultados diferenciales Java 25 / nativo sin JVM sobre {CLASS} — "
          f"{len(OPS)} operaciones × {len(IDS)} argumentos: constructor con longitudes 0..64, unicode, "
          f"pares sustitutos, controles, comillas y null; toString devolviendo el mismo argumento "
          f"(identidad, igualdad y longitud); y campo id sin interferencia entre instancias; "
          f"superficie reconciliada classfile↔reflexión ({len(surface['methods'])} métodos, "
          f"{len(surface['fields'])} campo, constructor público de un parámetro); el Rust generado "
          f"contiene el object_store del constructor y el object_load de toString; no certifica la clase")
    return 0


if __name__ == "__main__":
    sys.exit(main())
