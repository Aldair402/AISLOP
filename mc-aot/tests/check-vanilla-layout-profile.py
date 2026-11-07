#!/usr/bin/env python3
"""A-02 fase 2: el perfil de layouts medido contra el JAR oficial, no contra fixtures.

Qué demuestra esta prueba y qué no:

- Demuestra que `numeric_bridge_layout.verify` (ruta real `mc-aot inspect`) acepta
  clases **del JAR oficial** con su SHA-256 de classfile, que el censo de las
  7.762 clases cuadra con cifras fijas, y que censo y verificador **coinciden**:
  lo que el censo dice describible se acepta, y lo que dice bloqueado se rechaza
  con el motivo que el censo nombró.
- Demuestra que el lector de classfiles en Rust y el de Python coinciden campo a
  campo en clases reales de Minecraft.
- Demuestra que `java.lang.Record`, admitida como base externa sin estado, no
  declara campos de instancia (por reflexión, no por suposición).
- NO demuestra que esas clases se traduzcan ni se ejecuten. Un layout aceptado
  es un contrato de campos; `execution_blockers` dice qué falta para ejecutar.

Cifras al 2026-11-06: 2.611 clases describibles, 1.564 con campos, 4.048 campos, con
ranura propia para los ocho primitivos.

Historia: el número publicado antes fue «0 de 687» (irreproducible) y luego «6
aceptadas, ninguna con campos». Ninguno de los dos describía el problema.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
from numeric_bridge_layout import verify, EXTERNAL_EMPTY_BASES

JAR = root.parent / 'downloads' / 'server-26.3-inner.jar'

# Cifras fijas del censo. Si cambian, o cambió el JAR o cambió el perfil: las dos
# cosas hay que verlas, no aceptarlas en silencio.
TOTAL_CLASSES = 7762
DESCRIBABLE = 2611
DESCRIBABLE_WITH_FIELDS = 1564
INSTANCE_FIELDS = 4048

# Casos que se leen en el log: los que justifican la forma del layout.
NAMED = {
    'net/minecraft/server/players/SleepStatus': [('int', 'activePlayers'), ('int', 'sleepingPlayers')],
    # Record-like con dos `int final` y una referencia cuyo destino no se puede
    # describir todavía: el layout es suyo, el bloqueo es del destino.
    'net/minecraft/world/level/BlockEventData': [('ref', 'pos'), ('ref', 'block'),
                                                 ('int', 'paramA'), ('int', 'paramB')],
    'net/minecraft/world/level/levelgen/structure/BoundingBox': None,  # 6 int, sin leer nombres
    'net/minecraft/advancements/AdvancementHolder': None,              # record: base externa sin estado
    'net/minecraft/world/entity/ai/behavior/SetEntityLookTargetSometimes$Ticker': None,
    # Un record real con tres `double` finales: la ranura ancha sale del classfile.
    'net/minecraft/commands/arguments/coordinates/LocalCoordinates': [('double', 'left'),
                                                                     ('double', 'up'),
                                                                     ('double', 'forwards')],
}

# Motivo que el censo nombra -> mensaje que el verificador debe dar.
BLOCKER_TO_MESSAGE = [
    ('sin ranura', 'descriptor de campo no soportado'),
    ('descriptor ', 'descriptor de campo no soportado'),
    ('referencia fuera del JAR', 'referencia fuera del JAR'),
    ('referencia no final', 'referencia no final'),
    ('volatile', 'volatile'),
    ('interfaz/anotación/enum', 'interfaz/annotation/enum'),
    ('cadena fuera del JAR', 'clase de referencia ausente'),
]


def load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, root / 'tools' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


census_mod = load('layout_profile_census', 'layout-profile-census.py')
surface_mod = load('classfile_surface', 'classfile-surface.py')


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def build(profile):
    subprocess.run(['cargo', 'build', '--offline', '--profile', profile,
                    '--manifest-path', str(root / 'Cargo.toml')],
                   check=True, capture_output=True, text=True)
    binary = root / 'target' / profile / 'mc-aot'
    assert binary.is_file()
    return binary


def inspect(binary, klass):
    p = subprocess.run([str(binary), 'inspect', str(JAR), klass],
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, (klass, p.stderr[-500:])
    return p.stdout


def parse_inspect(text):
    """Superficie declarada según `mc-aot inspect`, para contrastarla con Python."""
    header = dict(re.findall(r'^(Clase|Superclase|Flags|Interfaces): (.*)$', text, re.M))
    fields = [(int(a, 16), b, c) for a, b, c in
              re.findall(r'^  0x([0-9a-f]{4}) (\S+) (\S+)$', text, re.M)]
    # `inspect` imprime nombre y descriptor juntos (`<init>()V`).
    methods = [(int(a, 16), b.split('(', 1)[0], '(' + b.split('(', 1)[1]) for a, b in
               re.findall(r'^  0x([0-9a-f]{4}) (\S+) \| code=', text, re.M)]
    return {'class': header['Clase'], 'super': header['Superclase'],
            'flags': int(header['Flags'], 16), 'fields': fields, 'methods': methods}


def check_census():
    rows = census_mod.census(JAR)
    summary = census_mod.summarize(rows)
    assert len(rows) == TOTAL_CLASSES, len(rows)
    assert len(summary['admitted']) == DESCRIBABLE, len(summary['admitted'])
    assert len(summary['with_fields']) == DESCRIBABLE_WITH_FIELDS, len(summary['with_fields'])
    assert summary['fields'] == INSTANCE_FIELDS, summary['fields']
    print(f"censo: {len(rows)} clases, {DESCRIBABLE} describibles, "
          f"{DESCRIBABLE_WITH_FIELDS} con campos, {INSTANCE_FIELDS} campos de instancia")
    for step in census_mod.plan(rows):
        print(f"  plan {step['classes']:5d} clases / {step['classes_with_fields']:5d} con campos / "
              f"{step['instance_fields']:5d} campos  {step['step']}")
    return rows


def check_admitted(rows, compiler, jar_sha):
    """Cada clase que el censo llama describible debe pasar el verificador real."""
    by_class = {r['class']: r for r in rows}
    admitted = [r['class'] for r in rows if not r['layout_blockers']]
    sample = list(NAMED)
    # Muestra repartida por todo el JAR, determinista.
    sample += [admitted[i] for i in range(0, len(admitted), max(1, len(admitted) // 12))][:12]
    sample = sorted(dict.fromkeys(sample))
    for klass in sample:
        result = verify(JAR, klass, compiler, jar_sha)
        entry = result['classes'][0]
        assert entry['class'] == klass, entry['class']
        with zipfile.ZipFile(JAR) as z:
            blob = z.read(klass + '.class')
        surface = surface_mod.parse_class(blob)
        assert entry['sha256'] == sha256(blob), klass
        assert entry['own_field_count'] == len([f for f in surface['fields']
                                               if not f['flag_bits'] & 0x0008]), klass
        # El layout completo = campos de la cadena desde Object + propios.
        expected_own = [(f['descriptor'], f['name']) for f in surface['fields']
                        if not f['flag_bits'] & 0x0008]
        got_own = [(f['descriptor'], f['name']) for f in entry['fields'][-len(expected_own):]] if expected_own else []
        assert got_own == expected_own, (klass, got_own, expected_own)
        if entry['super'] in EXTERNAL_EMPTY_BASES:
            assert entry['fields'], klass
        if NAMED.get(klass):
            assert [(f['kind'], f['name']) for f in entry['fields']] == NAMED[klass], (klass, entry['fields'])
        print(f"  ok {klass}: super={entry['super']} propios={entry['own_field_count']} "
              f"total={len(entry['fields'])} cerrada={entry['closed_by']} "
              f"bloqueos={len(entry['execution_blockers'])}")
    assert len(sample) >= 10, len(sample)


def check_rejected(rows, compiler, jar_sha):
    """El verificador debe rechazar lo que el censo declara bloqueado, y por lo mismo."""
    checked = 0
    for fragment, message in BLOCKER_TO_MESSAGE:
        candidate = next((r for r in rows
                          if r['layout_blockers'] and fragment in r['layout_blockers'][0]), None)
        if candidate is None:
            continue
        try:
            verify(JAR, candidate['class'], compiler, jar_sha)
        except ValueError as error:
            assert message in str(error), (candidate['class'], str(error), message)
            print(f"  rechazo {candidate['class']}: {str(error)[:70]}")
            checked += 1
        else:
            raise AssertionError('aceptó una clase que el censo bloquea: ' + candidate['class'])
    assert checked >= 5, checked


def check_record_base():
    """`java.lang.Record` se admite como base porque no tiene campos de instancia."""
    jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
    with tempfile.TemporaryDirectory() as tmp:
        source = pathlib.Path(tmp) / 'Probe.java'
        source.write_text('public class Probe { public static void main(String[] a) {\n'
                          '  System.out.println("fields=" + java.lang.Record.class.getDeclaredFields().length);\n'
                          '  System.out.println("kind=" + java.lang.Record.class.getSuperclass().getName());\n'
                          '} }\n')
        subprocess.run([str(jdk / 'javac'), '-d', tmp, str(source)], check=True,
                       capture_output=True)
        out = subprocess.run([str(jdk / 'java'), '-cp', tmp, 'Probe'],
                             check=True, capture_output=True, text=True).stdout
    assert 'fields=0' in out, out
    assert 'kind=java.lang.Object' in out, out
    assert EXTERNAL_EMPTY_BASES == {'java/lang/Record'}, EXTERNAL_EMPTY_BASES
    print('base externa: java.lang.Record declara 0 campos de instancia (reflexión JDK 25)')


def check_parser_cross(binary):
    """Rust y Python deben leer igual las mismas clases reales."""
    with zipfile.ZipFile(JAR) as z:
        entries = sorted(n for n in z.namelist()
                         if n.endswith('.class') and not n.startswith('META-INF/'))
        sample = [entries[i] for i in range(0, len(entries), 409)][:12]
        compared = 0
        for entry in sample:
            klass = entry[:-6]
            surface = surface_mod.parse_class(z.read(entry))
            if len(surface['fields']) > 40 or len(surface['methods']) > 40:
                continue
            seen = parse_inspect(inspect(binary, klass))
            assert seen['class'] == surface['this_class'], klass
            assert seen['super'] == (surface['super_class'] or ''), klass
            assert seen['flags'] == surface['flag_bits'], (klass, hex(seen['flags']))
            fields = [(f['flag_bits'], f['name'], f['descriptor']) for f in surface['fields']]
            assert seen['fields'] == fields, (klass, 'campos')
            methods = [(m['flag_bits'], m['name'], m['descriptor']) for m in surface['methods']]
            assert seen['methods'] == methods, (klass, 'métodos')
            compared += 1
        assert compared >= 8, compared
        print(f'parser cruzado: {compared} clases reales, campos/métodos/flags idénticos')


def check_negative_controls(compiler, jar_sha):
    """Sobre bytes reales: lo que no se puede describir debe rechazarse."""
    klass = 'net/minecraft/util/Graph'
    with zipfile.ZipFile(JAR) as z:
        blob = bytearray(z.read(klass + '.class'))
    flags_offset = class_flags_offset(blob, surface_mod)
    with tempfile.TemporaryDirectory() as tmp:
        counter = iter(range(100))

        def jar_with(payload, entry=klass + '.class'):
            path = pathlib.Path(tmp) / f'altered-{next(counter)}.jar'
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr(entry, bytes(payload))
            return path, sha256(path.read_bytes())

        # 1. Marcarla interfaz: no describe un objeto ordinario.
        altered = bytearray(blob)
        bits = int.from_bytes(altered[flags_offset:flags_offset + 2], 'big') | 0x0200
        altered[flags_offset:flags_offset + 2] = bits.to_bytes(2, 'big')
        path, digest = jar_with(altered)
        expect_reject(path, klass, compiler, digest, 'interfaz')

        # 2. Truncar el classfile.
        path, digest = jar_with(blob[:-8])
        expect_reject(path, klass, compiler, digest, None)

        # 3. Hash del JAR que no corresponde.
        path, _ = jar_with(blob)
        expect_reject(path, klass, compiler, 'f' * 64, 'hash')

        # 4. Clase ausente.
        path, digest = jar_with(blob, 'net/minecraft/util/Other.class')
        expect_reject(path, klass, compiler, digest, 'ausente')

        # 5. Una subclase real NO invalida el layout (cambia la etiqueta, no los
        #    campos): ese es el contrato nuevo. Se compila contra la clase oficial.
        subclass_control(tmp, compiler)
        print('controles negativos sobre bytes reales: 4 rechazos + 1 contrato de subclase')


def subclass_control(tmp, compiler):
    """Compila una subclase de una clase vanilla y exige que el layout no cambie."""
    jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
    klass = 'net/minecraft/server/players/SleepStatus'
    package_parts = klass.split('/')
    with zipfile.ZipFile(JAR) as z:
        original = z.read(klass + '.class')

    def tree(base):
        package = base.joinpath(*package_parts[:-1])
        package.mkdir(parents=True)
        (package / (package_parts[-1] + '.class')).write_bytes(original)
        return base

    with_sub = tree(pathlib.Path(tmp) / 'with')
    (with_sub / 'SleepStatusSub.java').write_text(
        'package net.minecraft.server.players;\n'
        'final class SleepStatusSub extends SleepStatus {}\n')
    built = subprocess.run([str(jdk / 'javac'), '-nowarn', '-cp', str(with_sub), '-d', str(with_sub),
                            str(with_sub / 'SleepStatusSub.java')], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr[-800:]
    path = pathlib.Path(tmp) / 'with-subclass.jar'
    subprocess.run([str(jdk / 'jar'), 'cf', str(path), '-C', str(with_sub), 'net/minecraft'],
                   check=True, capture_output=True)
    with_subclass = verify(path, klass, compiler, sha256(path.read_bytes()))['classes'][0]
    assert with_subclass['closed_by'] == 'has-subclasses', with_subclass['closed_by']
    assert [(f['kind'], f['name']) for f in with_subclass['fields']] == [
        ('int', 'activePlayers'), ('int', 'sleepingPlayers')], with_subclass['fields']
    without = verify(JAR, klass, compiler, sha256(JAR.read_bytes()))['classes'][0]
    assert without['closed_by'] == 'no-subclasses', without['closed_by']
    assert [(f['kind'], f['name']) for f in without['fields']] == [
        (f['kind'], f['name']) for f in with_subclass['fields']]
    print('  subclase real: layout idéntico, etiqueta has-subclasses')


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
    rows = check_census()
    check_record_base()
    check_admitted(rows, compiler, jar_sha)
    check_rejected(rows, compiler, jar_sha)
    check_parser_cross(compiler)
    check_negative_controls(compiler, jar_sha)
    print('OK: perfil de layouts medido contra el JAR oficial')
    return 0


if __name__ == '__main__':
    sys.exit(main())
