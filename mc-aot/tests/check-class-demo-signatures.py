#!/usr/bin/env python3
"""El driver de clase completa rechaza referencias en firmas antes de rustc."""
import os
import json
import importlib.util
import hashlib
import sys
import pathlib
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          timeout=180, **kwargs)


spec = importlib.util.spec_from_file_location('execution_census', root / 'tools/execution-census.py')
census_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census_module)
assert census_module.normalize('Error: invokestatic no soportado: java/lang/Math.max(FF)F\n  al compilar net/minecraft/Test.go()V') == 'invokestatic no soportado: <clase>.max(FF)F'

with tempfile.TemporaryDirectory(prefix='class-signatures-') as temp:
    d = pathlib.Path(temp)
    src = d / 'src/net/minecraft/test'
    src.mkdir(parents=True)
    cases = {
        'Primitive': 'public Primitive(int n) { this.n=n; } int n; public int value() { return n; }',
        'ReturnString': 'public ReturnString() {} public String value() { return "x"; }',
        'ArgObject': 'public ArgObject() {} public int value(Object x) { return 1; }',
        'CtorArray': 'public CtorArray(int[] x) {} public int value() { return 1; }',
        'ReturnArray': 'public ReturnArray() {} public int[] value() { return null; }',
    }
    for name, body in cases.items():
        (src / f'{name}.java').write_text(f'package net.minecraft.test; public class {name} {{ {body} }}')
    classes = d / 'classes'
    classes.mkdir()
    javac = run([jdk / 'javac', '-d', classes, *(src / f'{n}.java' for n in cases)])
    assert javac.returncode == 0, javac.stderr
    jar = d / 'test.jar'
    packed = run([jdk / 'jar', 'cf', jar, '-C', classes, '.'])
    assert packed.returncode == 0, packed.stderr

    for name in cases:
        fq = f'net/minecraft/test/{name}'
        rs = d / f'{name}.rs'
        generated = run([compiler, 'class-demo-rs', jar, fq, rs])
        binary = d / name
        compiled = run([compiler, 'class-demo', jar, fq, binary])
        if name == 'Primitive':
            assert generated.returncode == compiled.returncode == 0, (generated.stderr, compiled.stderr)
            assert rs.read_bytes() == pathlib.Path(str(binary) + '.rs').read_bytes()
            env = dict(os.environ, PATH='/nonexistent')
            result = run([binary, 'new', '7', '--', 'value'], env=env)
            assert result.returncode == 0 and result.stdout == 'OK\n7\n', (result.stdout, result.stderr)
        else:
            for result in (generated, compiled):
                assert result.returncode != 0 and 'referencia en firma fuera del driver:' in result.stderr, (name, result.stderr)
            assert not rs.exists() and not binary.exists(), name

    # El censo paralelo usa el JAR realmente suministrado y conserva el límite
    # generación ≠ compilación ni equivalencia semántica.
    report = d / 'census.json'
    census = run([sys.executable, root / 'tools/execution-census.py', '--jar', jar,
                  '--compiler', compiler, '--jobs', '2', '--out', report])
    assert census.returncode == 0, census.stderr
    data = json.loads(report.read_text())
    assert data['total'] == 5 and data['traducen_enteras'] == 1, data
    assert data['ok'] == ['net/minecraft/test/Primitive'], data['ok']
    assert data['jar_sha256'] == hashlib.sha256(jar.read_bytes()).hexdigest()
    assert data['compiler_sha256'] == hashlib.sha256(compiler.read_bytes()).hexdigest()
    assert all('referencia en firma fuera del driver' in reason for reason in data['fail'].values()), data['fail']

    print('OK: firmas primitivas compilan y ejecutan sin JVM; String, objeto y arrays rechazados antes de rustc; class-demo-rs y class-demo coinciden')
