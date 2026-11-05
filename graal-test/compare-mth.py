#!/usr/bin/env python3
"""Compara binarios mc-aot con métodos reales de Minecraft en una JVM Java 25."""
import hashlib
import os
import pathlib
import random
import subprocess
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parent.parent
here = pathlib.Path(__file__).resolve().parent
java_home = pathlib.Path(os.environ['JAVA_HOME'])
jar = root / 'downloads/server-26.3.jar'
examples = root / 'mc-aot/examples'
with tempfile.TemporaryDirectory(prefix='mc-mth-') as td:
    d = pathlib.Path(td)
    classpath = []
    with zipfile.ZipFile(jar) as z:
        for kind in ('libraries', 'versions'):
            for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
                checksum, _, rel = line.split('\t')
                safe = pathlib.PurePosixPath(rel)
                if safe.is_absolute() or '..' in safe.parts:
                    raise ValueError('ruta insegura en el JAR')
                data = z.read(f'META-INF/{kind}/{rel}')
                if hashlib.sha256(data).hexdigest() != checksum:
                    raise ValueError('checksum inválido: ' + rel)
                dest = d / kind / safe
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                classpath.append(str(dest))
    cp = os.pathsep.join(classpath)
    subprocess.run([str(java_home/'bin/javac'), '-cp', cp, '-d', str(d), str(here/'MthReference.java')], check=True)
    rng = random.Random(42)
    values = [-2147483648, -100, -1, 0, 1, 2, 3, 15, 16, 17, 46341, 50000, 1073741825, 2147483647]
    values += [rng.randint(-2147483648, 2147483647) for _ in range(100)]
    tuples = [(x, values[(i * 17 + 1) % len(values)], values[(i * 31 + 2) % len(values)]) for i, x in enumerate(values)]
    # Explicitly exercise divide-by-zero and Java's MIN_VALUE / -1 overflow case.
    tuples += [(0, 0, 0), (2147483647, 0, 0), (-2147483648, -1, 0), (-2147483648, 1, 0), (-7, 3, 0), (7, -3, 0)]
    tuples += [(x, 7, -7) for x in (179, 180, 181, -179, -180, -181, 359, 360, 361, -359, -360, -361)]
    tuples = [(x, y, z, values[(i * 7 + 5) % len(values)], values[(i * 11 + 6) % len(values)]) for i, (x, y, z) in enumerate(tuples)]
    tuples += [(0, 1, 20, -20, 1), (0, 1, 0, -20, 1), (0, 1, 0, 5, 1), (20, 1, 30, 0, 10)]
    inp = ''.join(f'{x},{y},{z},{w},{v}\n' for x, y, z, w, v in tuples)
    proc = subprocess.run([str(java_home/'bin/java'), '-cp', str(d)+os.pathsep+cp, 'MthReference'], input=inp, text=True, check=True, capture_output=True)
    lines = proc.stdout.splitlines()
    if len(lines) != len(tuples):
        raise RuntimeError(f'La JVM devolvió {len(lines)} resultados para {len(tuples)} entradas')
    for (x, y, z, w, v), line in zip(tuples, lines):
        expected = line.split(',')
        methods = [('mth-square', [x]), ('mth-power2', [x]), ('mth-abs', [x]),
                   ('mth-absmax', [x, y]), ('mth-clamp', [x, y, z]), ('mth-murmur', [x]),
                   ('mth-wrapdegrees', [x]), ('mth-ceildiv', [x, y]),
                   ('mth-roundtoward', [x, y]), ('mth-floordiv', [x, y]),
                   ('mth-modulo', [x, y]), ('mth-origin', [x, y, z, w, v]),
                   ('light-emission', [x, y]), ('light-blend', [x, y, z, w]),
                   ('biome-quantize', [x]), ('goal-tickdelay', [x]),
                   ('argb-multiply', [x, y]), ('argb-average', [x, y]), ('argb-blend', [x, y]),
                   ('mth-is-power2', [x])]
        if len(expected) != len(methods):
            raise RuntimeError('La JVM devolvió una cantidad inesperada de resultados')
        for (method, arguments), want in zip(methods, expected):
            native = subprocess.run([str(examples/method), *map(str, arguments)], text=True, capture_output=True)
            if want == 'ERR_ARITHMETIC':
                if native.returncode == 0 or 'ArithmeticException' not in native.stderr:
                    raise AssertionError(f'{method}{tuple(arguments)}: se esperaba error aritmético; nativo={native}')
            else:
                if native.returncode != 0 or native.stdout.strip() != want:
                    raise AssertionError(f'{method}{tuple(arguments)}: nativo={native.stdout!r} error={native.stderr!r}, Java={want}')
    print(f'OK: {len(tuples)*20} resultados coinciden con veinte métodos de Minecraft en Java 25 (errores aritméticos por categoría)')
