#!/usr/bin/env python3
"""Dos clases vanilla adicionales: todas sus declaraciones, diferencial JVM/nativo."""
import os
import pathlib
import random
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jar = root.parent / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
classes = [
    'net/minecraft/commands/arguments/selector/options/SetOnceOptionState',
    'net/minecraft/world/level/block/entity/BeaconBeamOwner$Section',
]

def run(args, **kw):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=180, **kw)

DRIVER = '''
public class Oracle {
  public static void main(String[] args) throws Exception {
    Class<?> c = Class.forName(args[0]); Object o = null;
    for (String step : args[1].split(";")) {
      String[] p = step.split(",");
      if (p[0].equals("new")) {
        o = p.length == 1 ? c.getConstructor().newInstance()
            : c.getConstructor(int.class).newInstance(Integer.parseInt(p[1]));
        System.out.println("OK");
      } else {
        Object v = c.getMethod(p[0]).invoke(o);
        if (v == null) System.out.println("OK");
        else if (v instanceof Boolean) System.out.println((Boolean)v ? "1" : "0");
        else System.out.println(v);
      }
    }
  }
}
'''

with tempfile.TemporaryDirectory(prefix='vanilla-two-') as td:
    d = pathlib.Path(td)
    (d / 'Oracle.java').write_text(DRIVER)
    result = run([jdk / 'javac', '-d', d, d / 'Oracle.java'])
    assert result.returncode == 0, result.stderr
    native_env = dict(os.environ, PATH='/nonexistent')
    rng = random.Random(20261107)
    for index, name in enumerate(classes):
        binary = d / f'bin{index}'
        result = run([compiler, 'class-demo', jar, name, binary])
        assert result.returncode == 0, (name, result.stderr)
        scenarios = []
        for i in range(50):
            if index == 0:
                steps = [['new']] + [[rng.choice(['canParse', 'markParsed'])] for _ in range(25)]
            else:
                color = [0, -1, -2147483648, 2147483647, rng.randint(-2147483648, 2147483647)][i % 5]
                steps = [['new', str(color)]] + [[rng.choice(['increaseHeight', 'getHeight', 'getColor'])] for _ in range(25)]
            scenarios.append(steps)
        for steps in scenarios:
            script = ';'.join(','.join(step) for step in steps)
            native_args = []
            for i, step in enumerate(steps):
                if i: native_args.append('--')
                native_args.extend(step)
            java = run([jdk / 'java', '-cp', f'{d}{os.pathsep}{jar}', 'Oracle', name.replace('/', '.'), script])
            native = run([binary, *native_args], env=native_env)
            assert java.returncode == native.returncode == 0, (name, java.stderr, native.stderr)
            assert java.stdout == native.stdout, (name, script, java.stdout, native.stdout)
        print(f'OK: {name}: constructor y todos los métodos declarados, 50 guiones Java 25 == nativo sin JVM')
