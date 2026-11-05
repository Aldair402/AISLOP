#!/usr/bin/env python3
"""QuartPos: superficie declarada + constructor privado + 5 métodos diferenciales.

C-03 exige que la superficie declarada se reconcilie con el classfile, incluidos
constructores y miembros privados. Este check hace tres cosas y las tres tienen
que pasar:

1. Lee el classfile del JAR con `mc-aot/tools/classfile-surface.py` (parser propio,
   sin JDK) y contrasta esa superficie con lo que reporta la reflexión de Java 25
   del mismo JAR: flags de clase, superclase, interfaces, campos declarados y
   constructores declarados. Dos lecturas independientes del mismo bytecode.
2. Ejecuta el constructor privado por reflexión en Java y registra lo observable:
   sin `setAccessible` lanza `IllegalAccessException`, con `setAccessible` construye
   una instancia. Ese comportamiento es **solo de Java**: el traductor no implementa
   reflexión, así que nativo no puede reproducirlo y se declara como límite, no como
   diferencial.
3. Mantiene el diferencial de los cinco métodos estáticos: 515 entradas int por
   método (límites de int incluidos) contra la ejecución nativa sin JVM.

No certifica la clase: un constructor inalcanzable salvo por reflexión no puede
contrastarse en nativo, y el contador del registro sigue en 0.
"""
import json, os, pathlib, random, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
JDK = pathlib.Path(os.environ["JAVA_HOME"]) / "bin"
JAR = PROJECT / "downloads/server-26.3-inner.jar"
CLASS = "net/minecraft/core/QuartPos"
CLASSFILE_TOOL = ROOT / "tools/classfile-surface.py"

REFLECT_DRIVER = """import net.minecraft.core.QuartPos;
import java.lang.reflect.*;
import java.util.*;

public class QuartReflect {
    static String mods(int m) {
        List<String> out = new ArrayList<>();
        if ((m & Modifier.PUBLIC) != 0) out.add("public");
        if ((m & Modifier.PRIVATE) != 0) out.add("private");
        if ((m & Modifier.PROTECTED) != 0) out.add("protected");
        if ((m & Modifier.STATIC) != 0) out.add("static");
        if ((m & Modifier.FINAL) != 0) out.add("final");
        if ((m & Modifier.ABSTRACT) != 0) out.add("abstract");
        return String.join(" ", out);
    }
    static String type(Class<?> c) {
        if (c == int.class) return "I";
        if (c == void.class) return "V";
        if (c == boolean.class) return "Z";
        if (c == long.class) return "J";
        return "L" + c.getName().replace('.', '/') + ";";
    }
    static String descriptor(Executable e) {
        StringBuilder sb = new StringBuilder("(");
        for (Class<?> p : e.getParameterTypes()) sb.append(type(p));
        sb.append(")").append(e instanceof Method ? type(((Method) e).getReturnType()) : "V");
        return sb.toString();
    }
    public static void main(String[] a) throws Exception {
        Class<?> k = QuartPos.class;
        System.out.println("class_mods=" + mods(k.getModifiers()));
        System.out.println("class_final=" + Modifier.isFinal(k.getModifiers()));
        System.out.println("super=" + (k.getSuperclass() == null ? "null" : k.getSuperclass().getName().replace('.', '/')));
        System.out.println("interfaces=" + k.getInterfaces().length);
        for (Field f : k.getDeclaredFields())
            System.out.println("field=" + f.getName() + ":" + type(f.getType()) + ":" + mods(f.getModifiers()));
        for (Method m : k.getDeclaredMethods())
            System.out.println("method=" + m.getName() + ":" + descriptor(m) + ":" + mods(m.getModifiers()));
        Constructor<?>[] ctors = k.getDeclaredConstructors();
        System.out.println("ctor_count=" + ctors.length);
        for (Constructor<?> c : ctors) {
            System.out.println("ctor=" + descriptor(c) + ":" + mods(c.getModifiers()) + ":params=" + c.getParameterCount());
            // Sin setAccessible: el idioma normal de Java desde fuera de la clase.
            try {
                c.newInstance();
                System.out.println("ctor_direct=instantiated");
            } catch (InvocationTargetException e) {
                System.out.println("ctor_direct=" + e.getCause().getClass().getName());
            } catch (Exception e) {
                System.out.println("ctor_direct=" + e.getClass().getName());
            }
            // Con setAccessible: reflexión que fuerza el acceso privado.
            try {
                c.setAccessible(true);
                Object o = c.newInstance();
                System.out.println("ctor_forced=" + o.getClass().getName().replace('.', '/'));
            } catch (InvocationTargetException e) {
                System.out.println("ctor_forced=" + e.getCause().getClass().getName());
            } catch (Exception e) {
                System.out.println("ctor_forced=" + e.getClass().getName());
            }
        }
        // Los cuatro campos no tienen por qué leerse aquí: eso ya lo hace el
        // diferencial de abajo contra el binario nativo.
        System.out.println("name=" + k.getName().replace('.', '/'));
    }
}
"""

STATIC_SPECS = [("fromBlock", "(I)I"), ("quartLocal", "(I)I"), ("toBlock", "(I)I"),
                ("fromSection", "(I)I"), ("toSection", "(I)I")]
FIELD_SPECS = ["BITS", "SIZE", "MASK", "SECTION_TO_QUARTS_BITS"]
FIELD_DESCRIPTORS = ["I"] * len(FIELD_SPECS)


def classfile_surface():
    out = subprocess.run([sys.executable, str(CLASSFILE_TOOL), CLASS.replace("/", "."), "--json"],
                         text=True, capture_output=True, check=True)
    return json.loads(out.stdout)


def java_reflection(directory):
    source = directory / "QuartReflect.java"
    source.write_text(REFLECT_DRIVER)
    subprocess.run([str(JDK / "javac"), "-cp", str(JAR), "-d", str(directory), str(source)],
                   check=True)
    run = subprocess.run([str(JDK / "java"), "-cp", f"{directory}{os.pathsep}{JAR}", "QuartReflect"],
                         text=True, capture_output=True, check=True, timeout=60)
    parsed = {"fields": {}, "methods": {}, "ctors": []}
    for line in run.stdout.splitlines():
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
            parsed[key] = value
    return parsed


def check_reconciliation(surface, reflect):
    problems = []

    # Flags y superclase: dos lecturas independientes del mismo bytecode.
    if "final" not in surface["flags"]:
        problems.append("classfile no marca la clase final")
    if reflect.get("class_final") != "true":
        problems.append(f"la reflexión no ve final=true: {reflect.get('class_final')}")
    if surface["super_class"] != reflect.get("super"):
        problems.append(f"superclase distinta: classfile={surface['super_class']} reflejo={reflect.get('super')}")
    if len(surface["interfaces"]) != int(reflect.get("interfaces", -1)):
        problems.append(f"interfaces distintas: classfile={surface['interfaces']} reflejo={reflect.get('interfaces')}")

    classfile_fields = {f"{m['name']}:{m['descriptor']}" for m in surface["fields"]}
    if classfile_fields != set(reflect["fields"]):
        problems.append(f"campos distintos: classfile={sorted(classfile_fields)} "
                        f"reflejo={sorted(reflect['fields'])}")

    # getDeclaredMethods() no incluye constructores: se comparan aparte, abajo.
    classfile_methods = {f"{m['name']}:{m['descriptor']}" for m in surface["methods"]
                         if m["name"] != "<init>"}
    if classfile_methods != set(reflect["methods"]):
        problems.append(f"métodos distintos: classfile={sorted(classfile_methods)} "
                        f"reflejo={sorted(reflect['methods'])}")

    # Modificadores por miembro: el parser y la reflexión deben coincidir.
    for member in surface["fields"] + surface["methods"]:
        key = f"{member['name']}:{member['descriptor']}"
        table = reflect["fields"] if member["name"] in FIELD_SPECS else reflect["methods"]
        if key in table:
            parsed = {f for f in member["flags"] if f in ("public", "private", "protected", "static", "final")}
            seen = set(table[key].split()) if table[key] else set()
            if parsed != seen:
                problems.append(f"flags de {key}: classfile={sorted(parsed)} reflejo={sorted(seen)}")

    # El constructor privado: la única laguna que tenía el inventario anterior.
    if not surface["has_init"]:
        problems.append("el classfile no declara <init>, pero la clase no es interfaz")
    if len(reflect["ctors"]) != 1:
        problems.append(f"se esperaba un constructor declarado, hay {len(reflect['ctors'])}")
    for ctor in reflect["ctors"]:
        if ctor["descriptor"] != "()V":
            problems.append(f"constructor inesperado {ctor['descriptor']}")
        if ctor["modifiers"] != "private":
            problems.append(f"el constructor debería ser private, es '{ctor['modifiers']}'")
        if ctor["params"] != "params=0":
            problems.append(f"el constructor debería no tener parámetros: {ctor['params']}")
    if reflect.get("ctor_direct") != "java.lang.IllegalAccessException":
        problems.append(f"sin setAccessible se esperaba IllegalAccessException, "
                        f"se observó {reflect.get('ctor_direct')}")
    if reflect.get("ctor_forced") != CLASS:
        problems.append(f"con setAccessible se esperaba una instancia de {CLASS}, "
                        f"se observó {reflect.get('ctor_forced')}")
    if problems:
        for p in problems:
            print(f"FALLO: {p}", file=sys.stderr)
        raise SystemExit(1)


def check_static_differential(directory):
    cmd = ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "Cargo.toml"), "--",
           "multi-static-demo", str(JAR), CLASS, str(directory / "native")]
    for name, desc in STATIC_SPECS:
        cmd.extend((name, desc))
    for name, desc in zip(FIELD_SPECS, FIELD_DESCRIPTORS):
        cmd.extend(("@" + name, desc))
    built = subprocess.run(cmd, text=True, capture_output=True, timeout=180)
    if built.returncode:
        raise SystemExit(built.stderr)

    rng = random.Random(263)
    values = [-2147483648, -2147483647, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 2147483646, 2147483647]
    values += [rng.randint(-2147483648, 2147483647) for _ in range(500)]
    args = [str(i) for i in range(len(STATIC_SPECS), len(STATIC_SPECS) + len(FIELD_SPECS))]
    for n in values:
        for op in range(len(STATIC_SPECS)):
            args.extend((str(op), str(n)))
    java = subprocess.run([str(JDK / "java"), "-cp", f"{directory}{os.pathsep}{JAR}", "QuartSurface", *args],
                          text=True, capture_output=True, check=True, timeout=60)
    native = subprocess.run([str(directory / "native"), *args], text=True, capture_output=True, timeout=60)
    if native.returncode or java.stdout != native.stdout:
        raise SystemExit(f"diferencial roto: java={java.stdout[:400]!r} nativo={native.stdout[:400]!r} "
                         f"stderr={native.stderr[:400]!r}")
    return len(values) * len(STATIC_SPECS) + len(FIELD_SPECS)


SURFACE_DRIVER = """import net.minecraft.core.QuartPos;import java.lang.reflect.*;
public class QuartSurface {public static void main(String[] a)throws Exception {for(int i=0;i<a.length;){int op=Integer.parseInt(a[i++]);if(op>=5){String[] names={"BITS","SIZE","MASK","SECTION_TO_QUARTS_BITS"};Field f=QuartPos.class.getDeclaredField(names[op-5]);f.setAccessible(true);System.out.println(f.getInt(null));continue;}int x=Integer.parseInt(a[i++]);System.out.println(switch(op){case 0->QuartPos.fromBlock(x);case 1->QuartPos.quartLocal(x);case 2->QuartPos.toBlock(x);case 3->QuartPos.fromSection(x);case 4->QuartPos.toSection(x);default->throw new AssertionError();});}}}"""


def main():
    if not JAR.is_file():
        print(f"ERROR: falta {JAR}; seguir la preparación del README", file=sys.stderr)
        return 2
    surface = classfile_surface()
    with tempfile.TemporaryDirectory(prefix="mc-quart-surface-") as tmp:
        directory = pathlib.Path(tmp)
        (directory / "QuartSurface.java").write_text(SURFACE_DRIVER)
        subprocess.run([str(JDK / "javac"), "-cp", str(JAR), "-d", str(directory),
                        str(directory / "QuartSurface.java")], check=True)
        reflect = java_reflection(directory)
        check_reconciliation(surface, reflect)
        results = check_static_differential(directory)

    print(f"OK: {results} resultados diferenciales de los cinco métodos estáticos y cuatro campos; "
          f"superficie reconciliada classfile↔reflexión ({len(surface['methods'])} métodos, "
          f"{len(surface['fields'])} campos, sin <clinit>); constructor privado medido como "
          f"solo-Java (IllegalAccessException sin setAccessible, instancia con setAccessible) y "
          f"declarado como límite porque el traductor no implementa reflexión; no certifica la clase")
    return 0


if __name__ == "__main__":
    sys.exit(main())
