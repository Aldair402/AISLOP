#!/usr/bin/env python3
"""A-02 fase 2: el perfil de layouts se mide contra el JAR oficial, no contra fixtures.

Qué demuestra esta prueba y qué no:

- Demuestra que `numeric_bridge_layout.verify` (ruta real `mc-aot inspect`) acepta
  clases **del JAR oficial** y produce un layout con su SHA-256, y que el censo
  de las 7.762 clases cuadra con una lista fija (así un cambio del parser o del
  perfil se nota).
- Demuestra que el lector de classfiles en Rust y el de Python, escritos por
  separado, coinciden campo a campo en clases reales de Minecraft.
- NO demuestra que esas clases se traduzcan ni se ejecuten. Un layout aceptado
  es un contrato de campos, no una clase soportada.

El censo explica además por qué el resto no entra: hoy el límite no son los
estáticos, es `final` (5.377 clases) y la superclase (1.527).
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
from numeric_bridge_layout import verify

JAR = root.parent / 'downloads' / 'server-26.3-inner.jar'

# Lista fija: si cambia, o cambió el JAR o cambió el perfil. Ambas cosas hay que
# verlas, no aceptarlas en silencio.
ADMITTED = [
    'net/minecraft/server/packs/resources/PreparableReloadListener$StateKey',
    'net/minecraft/util/Graph',
    'net/minecraft/world/effect/MobEffectUtil',
    'net/minecraft/world/entity/ai/behavior/LongJumpUtil',
    'net/minecraft/world/level/levelgen/NoiseRouterData$QuantizedSpaghettiRarity',
    'net/minecraft/world/waypoints/WaypointStyleAsset',
]
TOTAL_CLASSES = 7762
FIRST_BLOCKER_NO_FINAL = 5377
FIRST_BLOCKER_SUPER = 1527
# Plan medido (censo --plan): qué compra cada relajación. Se fija aquí porque es
# la única cifra que decide qué se implementa después de A-02.
PLAN = [
    (6, 0, 0),
    (9, 0, 0),
    (291, 1, 2),
    (470, 5, 10),
    (651, 186, 375),
]


def load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, root / 'tools' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


census_mod = load('layout_profile_census', 'layout-profile-census.py')
surface_mod = load('classfile_surface', 'classfile-surface.py')


def build(profile):
    out = subprocess.run(['cargo', 'build', '--offline', '--profile', profile,
                          '--manifest-path', str(root / 'Cargo.toml')],
                         check=True, capture_output=True, text=True)
    binary = root / 'target' / profile / 'mc-aot'
    assert binary.is_file(), out.stderr[-2000:]
    return binary


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def inspect(binary, jar, klass):
    p = subprocess.run([str(binary), 'inspect', str(jar), klass],
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, (klass, p.stderr[-500:])
    return p.stdout


def parse_inspect(text):
    """Superficie declarada según `mc-aot inspect`, para contrastarla con Python."""
    header = dict(re.findall(r'^(Clase|Superclase|Flags|Interfaces): (.*)$', text, re.M))
    fields = [m.groups() for m in re.finditer(r'^  0x([0-9a-f]{4}) (\S+) (\S+)$', text, re.M)]
    # `inspect` imprime nombre y descriptor juntos (`<init>()V`), igual que el
    # verificador; se separan aquí para comparar con el parser de Python.
    methods = [(int(a, 16), b.split('(', 1)[0], '(' + b.split('(', 1)[1])
               for a, b in re.findall(r'^  0x([0-9a-f]{4}) (\S+) \| code=', text, re.M)]
    return {'class': header['Clase'], 'super': header['Superclase'],
            'flags': int(header['Flags'], 16),
            'fields': [(int(a, 16), b, c) for a, b, c in fields],
            'methods': methods}


def check_census(jar_sha):
    """El censo del JAR oficial debe dar exactamente lo registrado."""
    rows = census_mod.census(JAR, False)
    assert len(rows) == TOTAL_CLASSES, f'clases en el JAR: {len(rows)} != {TOTAL_CLASSES}'
    closed = sorted(census_mod.closure_admitted(rows))
    assert closed == ADMITTED, ('admitidas cambiaron', closed)
    first = census_mod.summarize(rows)['first_blocker']
    assert first['clase-no-final'] == FIRST_BLOCKER_NO_FINAL, first['clase-no-final']
    assert first['superclase'] == FIRST_BLOCKER_SUPER, first['superclase']
    steps = census_mod.plan(rows)
    got = [(x['classes'], x['classes_with_fields'], x['instance_fields']) for x in steps]
    assert got == PLAN, ('el plan cambió', got)
    for step, numbers in zip(steps, got):
        print(f"  plan {numbers[0]:5d} clases / {numbers[1]:5d} con campos / {numbers[2]:5d} campos  {step['step']}")
    print(f'censo: {len(rows)} clases, {len(closed)} admitidas con grafo cerrado, '
          f'{first["clase-no-final"]} bloqueadas por `final`, {first["superclase"]} por superclase')
    return rows


def check_admitted(jar_sha, compiler, rows):
    """Cada clase admitida por el censo debe pasar el verificador real."""
    by_class = {r['class']: r for r in rows}
    for klass in ADMITTED:
        result = verify(JAR, klass, compiler, jar_sha)
        assert result['root'] == klass
        assert result['jar_sha256'] == jar_sha
        classes = result['classes']
        assert classes[0]['class'] == klass, classes[0]['class']
        with zipfile.ZipFile(JAR) as z:
            blob = z.read(klass + '.class')
        assert classes[0]['sha256'] == sha256(blob), 'hash de clase distinto del classfile'
        # El layout debe describir los mismos campos, en el mismo orden, que el
        # classfile: si el perfil cambia de orden sin cambiar de bytes, esto falla.
        surface = surface_mod.parse_class(blob)
        expected = []
        for field in surface['fields']:
            if field['flag_bits'] & 0x0008:
                continue
            descriptor = field['descriptor']
            if descriptor == 'I':
                expected.append(('int', field['name'], None))
            else:
                kind = 'ref' if field['flag_bits'] & 0x0010 else 'mutref'
                expected.append((kind, field['name'], descriptor[1:-1]))
        got = [(f['kind'], f['name'], f.get('target')) for f in classes[0]['fields']]
        assert got == expected, (klass, got, expected)
        print(f'  layout aceptado {klass} ({len(got)} campos, sha {classes[0]["sha256"][:12]})')
    assert len(by_class) == TOTAL_CLASSES


def check_parser_cross(binary):
    """Rust y Python deben leer igual las mismas clases reales."""
    with zipfile.ZipFile(JAR) as z:
        entries = sorted(n for n in z.namelist()
                         if n.endswith('.class') and not n.startswith('META-INF/'))
        sample = [entries[i] for i in range(0, len(entries), 409)]
        sample = sample[:12]
        compared = 0
        for entry in sample:
            klass = entry[:-6]
            blob = z.read(entry)
            surface = surface_mod.parse_class(blob)
            if len(surface['fields']) > 40 or len(surface['methods']) > 40:
                continue
            seen = parse_inspect(inspect(binary, JAR, klass))
            assert seen['class'] == surface['this_class'], (klass, seen['class'])
            assert seen['super'] == (surface['super_class'] or ''), klass
            assert seen['flags'] == surface['flag_bits'], (klass, hex(seen['flags']))
            fields = [(f['flag_bits'], f['name'], f['descriptor']) for f in surface['fields']]
            assert seen['fields'] == fields, (klass, 'campos', seen['fields'], fields)
            methods = [(m['flag_bits'], m['name'], m['descriptor']) for m in surface['methods']]
            assert seen['methods'] == methods, (klass, 'métodos', seen['methods'], methods)
            assert ('<clinit>' in [m[1] for m in seen['methods']]) == surface['has_clinit'], klass
            compared += 1
        assert compared >= 8, f'solo {compared} clases comparadas'
        print(f'parser cruzado: {compared} clases reales, campos/métodos/flags idénticos')


def check_negative_controls(jar_sha, compiler):
    """Sobre bytes reales: si se altera el classfile, el perfil debe rechazarlo."""
    klass = 'net/minecraft/util/Graph'
    with zipfile.ZipFile(JAR) as z:
        blob = bytearray(z.read(klass + '.class'))
    flags_offset = class_flags_offset(blob, surface_mod)
    with tempfile.TemporaryDirectory() as tmp:
        def jar_with(payload, entry=klass + '.class'):
            path = pathlib.Path(tmp) / 'altered.jar'
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr(entry, bytes(payload))
            return path, sha256(path.read_bytes())

        # 1. Quitar ACC_FINAL de una clase real: ya no es un tipo cerrado.
        altered = bytearray(blob)
        altered[flags_offset:flags_offset + 2] = (int.from_bytes(
            altered[flags_offset:flags_offset + 2], 'big') & ~0x0010).to_bytes(2, 'big')
        path, digest = jar_with(altered)
        expect_reject(path, klass, compiler, digest, 'final')

        # 2. Marcarla abstracta: aunque conserve los bytes, el perfil no la admite.
        altered = bytearray(blob)
        altered[flags_offset:flags_offset + 2] = (int.from_bytes(
            altered[flags_offset:flags_offset + 2], 'big') | 0x0400).to_bytes(2, 'big')
        path, digest = jar_with(altered)
        expect_reject(path, klass, compiler, digest, 'abstracta')

        # 3. Truncar el classfile: no se puede inventar un layout de bytes cortados.
        path, digest = jar_with(blob[:-8])
        expect_reject(path, klass, compiler, digest, None)

        # 4. Hash del JAR que no corresponde: el layout dejaría de estar atado a
        #    los bytes que se compilaron.
        path, _ = jar_with(blob)
        expect_reject(path, klass, compiler, 'f' * 64, 'hash')

        # 5. Clase ausente: un grafo no se completa con huecos.
        path, digest = jar_with(blob, 'net/minecraft/util/Other.class')
        expect_reject(path, klass, compiler, digest, 'ausente')
        print('controles negativos sobre bytes reales: 5 rechazos')


def class_flags_offset(blob, module):
    """Offset de access_flags: tras el constant pool. Sin JDK ni supuestos."""
    reader = module.Reader(bytes(blob))
    assert reader.u4() == 0xCAFEBABE
    reader.u2(), reader.u2()
    module.parse_constant_pool(reader)
    return reader.pos


def expect_reject(path, klass, compiler, digest, wanted):
    try:
        verify(path, klass, compiler, digest)
    except ValueError as error:
        if wanted is not None and wanted not in str(error):
            raise AssertionError((klass, str(error), wanted)) from error
    else:
        raise AssertionError('no rechazó ' + klass)


def main():
    if not JAR.is_file():
        print(f'ERROR: falta {JAR}', file=sys.stderr)
        return 2
    jar_sha = sha256(JAR.read_bytes())
    compiler = build('release')
    rows = check_census(jar_sha)
    check_admitted(jar_sha, compiler, rows)
    check_parser_cross(compiler)
    check_negative_controls(jar_sha, compiler)
    print('OK: perfil de layouts medido contra el JAR oficial')
    return 0


if __name__ == '__main__':
    sys.exit(main())
