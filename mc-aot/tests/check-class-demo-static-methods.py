#!/usr/bin/env python3
"""El perfil de clase entera traduce métodos estáticos sin omitir instancias."""
import os
import pathlib
import random
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
source = '''package net.minecraft.test;
public class Mixed {
  private int value;
  public Mixed(int value) { this.value=value; }
  public static int increment(int v) { return v+1; }
  public static long plus(long v) { return v+5L; }
  public static float identity(float v) { return v; }
  public static String label() { return "static"; }
  public static void noop() { }
  public static int viaDependency() { return Helper.next(); }
  public void bump() { value=increment(value); }
  public int value() { return value; }
}'''
driver = '''import net.minecraft.test.Mixed;
public class Oracle {
  public static void main(String[] args) {
    Mixed x=null;
    for (String raw : args[0].split(";")) {
      String[] p=raw.split(",");
      switch(p[0]) {
        case "new": x=new Mixed(Integer.parseInt(p[1])); System.out.println("OK"); break;
        case "increment": System.out.println(Mixed.increment(Integer.parseInt(p[1]))); break;
        case "plus": System.out.println(Mixed.plus(Long.parseLong(p[1]))); break;
        case "identity": System.out.printf("fbits:%08x%n",Float.floatToRawIntBits(Mixed.identity(Float.parseFloat(p[1])))); break;
        case "label": System.out.println("s16:007300740061007400690063"); break;
        case "noop": Mixed.noop(); System.out.println("OK"); break;
        case "viaDependency": System.out.println(Mixed.viaDependency()); break;
        case "bump": x.bump(); System.out.println("OK"); break;
        case "value": System.out.println(x.value()); break;
        default: throw new AssertionError(p[0]);
      }
    }
  }
}'''

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=180, **kwargs)

with tempfile.TemporaryDirectory(prefix='class-static-') as tmp:
    d = pathlib.Path(tmp)
    (d/'Mixed.java').write_text(source)
    (d/'Oracle.java').write_text(driver)
    (d/'Helper.java').write_text('package net.minecraft.test; public class Helper { static int value=6; public static int next(){return ++value;} }')
    # La inicialización estática, la sobrecarga y los nombres reservados no se
    # traducen parcialmente; cada clase debe fallar antes de generar binario.
    bad = {
        'Clinit': 'public static int x=1; public Clinit() {} public static int get(){return x;}',
        'Overload': 'public Overload() {} public static int f(int n){return n;} public int f(){return 0;}',
        'Reserved': 'public Reserved() {} public int read(){return 0;}',
        'Reference': 'public Reference() {} public static int f(Object x){return 0;}',
        'CtorHandler': 'public CtorHandler() { try { Integer.parseInt(\"x\"); } catch (NumberFormatException e) { } }',
    }
    for name, body in bad.items():
        (d/f'{name}.java').write_text(f'package net.minecraft.test; public class {name} {{ {body} }}')
    javac = run([jdk/'javac', '-d', d, d/'Mixed.java', d/'Helper.java', d/'Oracle.java', *(d/f'{n}.java' for n in bad)])
    assert javac.returncode == 0, javac.stderr
    jar = d/'fixture.jar'
    packed = run([jdk/'jar', 'cf', jar, '-C', d, 'net'])
    assert packed.returncode == 0, packed.stderr
    binary = d/'native'
    compiled = run([compiler, 'class-demo', jar, 'net/minecraft/test/Mixed', binary])
    assert compiled.returncode == 0, compiled.stderr
    rng = random.Random(311)
    steps = [['increment','2147483647'], ['plus','9223372036854775807'],
             ['identity','-0.0'], ['label'], ['noop'], ['viaDependency'], ['viaDependency'], ['new','2147483647']]
    for _ in range(100):
        op = rng.choice(['increment', 'plus', 'identity', 'bump', 'value', 'label', 'noop', 'viaDependency'])
        if op == 'increment': steps.append([op, str(rng.randint(-2147483648,2147483647))])
        elif op == 'plus': steps.append([op, str(rng.randint(-9223372036854775808,9223372036854775807))])
        elif op == 'identity': steps.append([op, rng.choice(['0.0','-0.0','1.5','-123.25'])])
        else: steps.append([op])
    script = ';'.join(','.join(step) for step in steps)
    native_args = []
    for i, step in enumerate(steps):
        if i: native_args.append('--')
        native_args.extend(step)
    java = run([jdk/'java', '-cp', d, 'Oracle', script])
    native = run([binary, *native_args], env=dict(os.environ, PATH='/nonexistent'))
    assert java.returncode == native.returncode == 0, (java.stderr, native.stderr)
    assert java.stdout == native.stdout, (java.stdout, native.stdout)
    for name, reason in [('Clinit','<clinit> fuera del perfil'),
                         ('Overload','sobrecarga fuera del driver'),
                         ('Reserved','nombre reservado por el driver'),
                         ('Reference','referencia en firma fuera del driver'),
                         ('CtorHandler','constructor native/abstract o con manejadores fuera del driver')]:
        output = d/f'bad-{name}'
        rejected = run([compiler, 'class-demo', jar, f'net/minecraft/test/{name}', output])
        assert rejected.returncode != 0 and reason in rejected.stderr and not output.exists(), (name, rejected.stderr)
    print(f'OK: {len(steps)} pasos Java == nativo sin JVM; estáticos antes y después de new, init de dependencia, instancias, long, float, String y guardas')
