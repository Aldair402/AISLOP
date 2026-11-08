#!/usr/bin/env python3
"""A-02 fase 3: una clase vanilla **completa** traducida y ejecutada sin JVM.

La clase se elige con dos censos ya existentes, no a ojo: cae en el perfil de
layouts y no tiene bloqueo de ejecución (sin estáticos, sin `<clinit>`, sin
interfaces). Se compilan **todas** sus declaraciones —constructor incluido— y se
compara la salida del binario nativo con la misma secuencia ejecutada por Java 25
sobre el JAR oficial.

No dice nada sobre arrancar el servidor: `Main` sigue bloqueado.
"""
import importlib.util
import os
import pathlib
import random
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
project = root.parent
jar = project / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
CENSUS = root / 'tools' / 'layout-profile-census.py'

CLASS = 'net/minecraft/util/TickThrottler'
FIELDS = ['count', 'threshold', 'incrementStep']


def census():
    spec = importlib.util.spec_from_file_location('layout_profile_census', CENSUS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.census(jar)


def run(args, **kwargs):
    kwargs.setdefault('timeout', 300)
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


DRIVER = r'''
import java.lang.reflect.*;
public class Driver {
  public static void main(String[] argv) throws Exception {
    Object o = null;
    for (String raw : argv[0].split(";")) {
      if (raw.isEmpty()) continue;
      String[] t = raw.split(",");
      if (t[0].equals("new")) {
        Class<?> c = Class.forName("net.minecraft.util.TickThrottler");
        Constructor<?> k = c.getDeclaredConstructor(int.class, int.class);
        k.setAccessible(true);
        o = k.newInstance(Integer.parseInt(t[1]), Integer.parseInt(t[2]));
        System.out.println("OK");
      } else if (t[0].equals("read")) {
        Field f = o.getClass().getDeclaredField(t[1]);
        f.setAccessible(true);
        print(f.get(o));
      } else {
        Method m = null;
        for (Method cand : o.getClass().getDeclaredMethods()) {
          if (cand.getName().equals(t[0]) && cand.getParameterCount() == t.length - 1) m = cand;
        }
        if (m == null) throw new AssertionError("método ausente: " + t[0]);
        m.setAccessible(true);
        Class<?>[] pt = m.getParameterTypes();
        Object[] pv = new Object[pt.length];
        for (int i = 0; i < pt.length; i++) {
          String s = t[i + 1];
          if (pt[i] == int.class) pv[i] = Integer.parseInt(s);
          else if (pt[i] == long.class) pv[i] = Long.parseLong(s);
          else if (pt[i] == float.class) pv[i] = Float.parseFloat(s);
          else if (pt[i] == double.class) pv[i] = Double.parseDouble(s);
          else throw new AssertionError("parámetro no primitivo: " + pt[i]);
        }
        Object r = m.invoke(o, pv);
        if (m.getReturnType() == void.class) System.out.println("OK");
        else print(r);
      }
    }
  }
  static void print(Object v) {
    if (v instanceof Boolean) System.out.println(((Boolean) v) ? 1 : 0);
    else if (v instanceof Float) System.out.println(String.format("fbits:%08x", Float.floatToRawIntBits((Float) v)));
    else if (v instanceof Double) System.out.println(String.format("dbits:%016x", Double.doubleToRawLongBits((Double) v)));
    else System.out.println(v);
  }
}
'''


def native_args(binary, steps):
    args = [str(binary)]
    for i, step in enumerate(steps):
        if i:
            args.append('--')
        args.extend(step)
    return args


def as_script(steps):
    return ';'.join(','.join(step) for step in steps)


with tempfile.TemporaryDirectory(prefix='mc-first-class-') as td:
    d = pathlib.Path(td)
    binary = d / 'tick-throttler'
    build = run([str(compiler), 'class-demo', str(jar), CLASS, str(binary)],
                env={**os.environ, 'PATH': os.environ['PATH']})
    assert build.returncode == 0, build.stderr[-2000:]
    assert binary.is_file(), 'no se generó el binario'

    # 1) La clase estaba en el conjunto admitido por los dos censos.
    _, rows = census()
    row = next((r for r in rows if r['class'] == CLASS), None)
    assert row is not None, CLASS
    assert not row['layout_blockers'], row['layout_blockers']
    assert not row['execution_blockers'], row['execution_blockers']

    # 2) Sin Java en PATH: el binario no puede colarse a la JVM.
    native_env = {k: v for k, v in os.environ.items() if k != 'JAVA_HOME'}
    native_env['PATH'] = '/nonexistent'
    smoke = run(native_args(binary, [['new', '2', '5'], ['increment'], ['read', 'count'],
                                    ['increment'], ['isUnderThreshold'],
                                    ['tick'], ['tick'], ['tick'], ['tick'], ['tick'],
                                    ['read', 'count']]), env=native_env)
    assert smoke.returncode == 0, smoke.stderr
    assert smoke.stdout.split('\n')[:11] == ['OK', 'OK', '2', 'OK', '1', 'OK', 'OK', 'OK', 'OK', 'OK', '0'], smoke.stdout

    # 3) Diferencial: 120 guiones contra Java 25 sobre el JAR oficial.
    (d / 'Driver.java').write_text(DRIVER)
    javac = run([str(jdk / 'javac'), '-d', str(d), str(d / 'Driver.java')])
    assert javac.returncode == 0, javac.stderr[-1500:]
    rng = random.Random(20261107)
    compared = 0
    for _ in range(120):
        steps = [['new', str(rng.randint(0, 3)), str(rng.randint(-2, 6))]]
        for _ in range(rng.randint(4, 12)):
            op = rng.choice(['increment', 'tick', 'isUnderThreshold', 'read'])
            steps.append(['read', rng.choice(FIELDS)] if op == 'read' else [op])
        native = run(native_args(binary, steps), env=native_env)
        java = run([str(jdk / 'java'), '-cp', f'{jar}{os.pathsep}{d}', 'Driver', as_script(steps)])
        assert java.returncode == 0, java.stderr[-800:]
        assert native.returncode == 0, (steps, native.stderr)
        assert native.stdout == java.stdout, (as_script(steps), native.stdout, java.stdout)
        compared += 1

    # 4) Guardas del driver: no adivina pasos, campos ni orden.
    for steps, expected in (([['bogus']], 'paso desconocido'),
                            ([['read', 'count']], 'objeto no construido'),
                            ([['new', '1', '1'], ['read', 'incrementStep'], ['read', 'nope']], 'campo inexistente')):
        bad = run(native_args(binary, steps), env=native_env)
        assert bad.returncode == 2, (steps, bad.returncode)
        assert expected in bad.stderr, (steps, bad.stderr)

    # 5) Controles negativos: un bloqueo real del censo por categoría, y el
    #    compilador tiene que decir cuál es; no basta con fallar.
    wanted = {
        'clinit': ('<clinit> fuera del perfil',
                   lambda r: 'clinit' in r['execution_blockers']),
        'estáticos': ('campo estático fuera del perfil',
                      lambda r: 'campos estáticos' in r['execution_blockers']
                      and 'clinit' not in r['execution_blockers']),
        'interfaces': ('interfaces fuera del perfil',
                       lambda r: 'interfaces' in r['execution_blockers']),
        'ref': ('campo no primitivo fuera del perfil',
                lambda r: 'referencia fuera del JAR' in r['layout_blockers']),
    }
    used, controls = set(), {}
    for label, (reason, matches) in wanted.items():
        for r in rows:
            if r['class'] in used or not matches(r):
                continue
            out = run([str(compiler), 'class-demo', str(jar), r['class'], str(d / f'reject-{label}')])
            if out.returncode != 0 and reason in out.stdout + out.stderr:
                used.add(r['class'])
                controls[label] = (r['class'], reason)
                assert not (d / f'reject-{label}').exists(), (label, r['class'])
                break
    assert len(controls) == 4, controls

    print(f'OK: {CLASS} completa (constructor + 3 métodos) traducida y ejecutada sin JVM; '
          f'{compared} guiones idénticos a Java 25; campos leídos {FIELDS}; '
          'guardas de paso/campo/orden; cuatro bloqueos del censo rechazados con su nombre; no Main')
