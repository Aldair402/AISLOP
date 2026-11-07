#!/usr/bin/env python3
"""Pruebas aisladas del validador A-02; no ejercitan Main ni certifican clases.

Lo que este test fija, y por qué cambió (2026-11-06):

- El layout describe **estado de instancia**. Campos estáticos, `<clinit>` e
  interfaces se anotan como bloqueos de *ejecución*, no como rechazo del layout.
- El layout incluye los **campos heredados primero** (prefijo), de modo que un
  campo declarado en el padre tiene el mismo índice en cualquier descendiente.
  El objeto se ata con el layout de su clase exacta, así que una subclase no
  traducida falla cerrada en `attach`.
- `final` en un campo `int` es una restricción de escritura, no otra ranura: se
  acepta y se anota; lo que sigue rechazándose es un descriptor sin ranura
  (`J/F/D/Z/B/C/S`), `volatile`, arrays y referencias a tipos sin bytes en el JAR.
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import warnings
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
from numeric_bridge_layout import verify, rust_layouts

java = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
subprocess.run(['cargo', 'build', '--offline', '--manifest-path', str(root/'Cargo.toml')], check=True, stdout=subprocess.DEVNULL)
compiler = root/'target/debug/mc-aot'
source = '''package net.minecraft.layouttest;
final class Valid { int x; final Target link; Valid(Target t) { link=t; } }
final class Target { int y; final Valid link; Target(Valid v) { link=v; } }
final class Empty {}
final class Reverse { final Reverse link=null; int value; }
final class MutableRef2 { MutableRef2 link=null; int value; }
final class MutableRef { Target x; }
class NonFinal { int x; }
class Parent { int base; }
final class Child extends Parent { final Target other=null; }
interface Tag {}
class HasInterface implements Tag { int x; }
final class StaticField { static final int X=1; int y; }
final class Initializer { static { System.out.println("init"); } int y; }
final class FinalInt { final int x=1; }
final class VolatileInt { volatile int z; }
final class VolatileRef { volatile Target z=null; }
final class BooleanField { boolean b; }
final class ByteField { byte b; }
final class CharField { char c; }
final class ShortField { short s; }
final class LongField { long j; }
final class FloatField { float f; }
final class DoubleField { double d; }
final class ArrayRef { final int[] a = null; }
final class StringRef { final String s = null; }
class ParentTarget { int y; }
final class ParentSub extends ParentTarget {}
final class InvalidTarget { final ParentTarget x = null; }
'''

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rejected(jar, name, expected, wanted=None):
    try:
        verify(jar, 'net/minecraft/layouttest/'+name, compiler, expected)
    except ValueError as e:
        if wanted is not None and wanted not in str(e):
            raise AssertionError((name, str(e), wanted)) from e
    else:
        raise AssertionError('no rechazó ' + name)

def accepted(jar, name, expected, allow_mutable=False):
    return verify(jar, 'net/minecraft/layouttest/'+name, compiler, expected, allow_mutable)

with tempfile.TemporaryDirectory(prefix='mc-bridge-layout-') as tmp:
    d=pathlib.Path(tmp)
    (d/'Classes.java').write_text(source)
    subprocess.run([str(java/'javac'), '-d', str(d), str(d/'Classes.java')], check=True)
    jar=d/'classes.jar'
    with zipfile.ZipFile(jar, 'w') as z:
        for p in sorted((d/'net').rglob('*.class')):
            z.write(p, p.relative_to(d).as_posix())
    h=digest(jar)
    result=accepted(jar, 'Valid', h)
    assert [x['class'].split('/')[-1] for x in result['classes']] == ['Valid', 'Target']
    assert [[x['kind'] for x in c['fields']] for c in result['classes']] == [['int','ref'],['int','ref']]
    assert all(len(c['sha256']) == 64 for c in result['classes'])
    assert result['schema'] == 'numeric-graph-layout-v2', result['schema']
    rust=rust_layouts(result)
    assert 'static LAYOUT_0:' in rust and 'static LAYOUT_1:' in rust
    assert 'NumericGraphSlot::Ref("net/minecraft/layouttest/Target")' in rust
    empty=accepted(jar, 'Empty', h)
    assert empty['classes'][0]['fields'] == []
    reverse=accepted(jar, 'Reverse', h)
    assert [x['kind'] for x in reverse['classes'][0]['fields']] == ['ref','int']
    assert 'fields:&[NumericGraphSlot::Ref("net/minecraft/layouttest/Reverse"),NumericGraphSlot::Int]' in rust_layouts(reverse)
    try:
        verify(jar, 'net/minecraft/layouttest/MutableRef2', compiler, h)
    except ValueError as e:
        assert 'referencia no final' in str(e), e
    else:
        raise AssertionError('aceptó referencia mutable sin opt-in')
    mutable=accepted(jar, 'MutableRef2', h, True)
    assert [x['kind'] for x in mutable['classes'][0]['fields']]==['mutref','int']
    assert 'NumericGraphSlot::MutRef("net/minecraft/layouttest/MutableRef2")' in rust_layouts(mutable)
    rejected_mutable=accepted(jar, 'MutableRef', h, True)
    assert [x['kind'] for x in rejected_mutable['classes'][0]['fields']]==['mutref']

    # Herencia: prefijo del padre primero y la clase exacta en el layout.
    child=accepted(jar, 'Child', h)
    entry=child['classes'][0]
    assert entry['super']=='net/minecraft/layouttest/Parent', entry['super']
    assert entry['closed_by']=='final', entry['closed_by']
    assert entry['own_field_count']==1, entry['own_field_count']
    assert [(f['name'], f.get('declared_in')) for f in entry['fields']] == [
        ('base','net/minecraft/layouttest/Parent'), ('other','net/minecraft/layouttest/Child')], entry['fields']
    assert 'fields:&[NumericGraphSlot::Int,NumericGraphSlot::Ref("net/minecraft/layouttest/Target")]' in rust_layouts(child)
    parent=accepted(jar, 'Parent', h)
    assert parent['classes'][0]['closed_by']=='has-subclasses', parent['classes'][0]['closed_by']
    # Un padre con subclases sigue siendo describible; lo que no se promete es que
    # una instancia de la subclase quepa en su layout: `attach` exige clase exacta.
    assert parent['classes'][0]['own_field_count']==1
    nonfinal=accepted(jar, 'NonFinal', h)
    assert nonfinal['classes'][0]['closed_by']=='no-subclasses', nonfinal['classes'][0]['closed_by']

    # Lo que bloquea la *ejecución* se anota, no rechaza el layout.
    static=accepted(jar, 'StaticField', h)
    assert 'campos estáticos' in static['classes'][0]['execution_blockers'], static['classes'][0]
    assert [f['name'] for f in static['classes'][0]['fields']]==['y']
    init=accepted(jar, 'Initializer', h)
    assert 'clinit' in init['classes'][0]['execution_blockers'], init['classes'][0]
    iface=accepted(jar, 'HasInterface', h)
    assert any(b.startswith('interfaces') for b in iface['classes'][0]['execution_blockers']), iface['classes'][0]
    finalint=accepted(jar, 'FinalInt', h)
    assert finalint['classes'][0]['fields'][0]['final'] is True, finalint['classes'][0]['fields'][0]

    cases={
        'Tag':'interfaz/annotation/enum',
        'VolatileInt':'volatile', 'VolatileRef':'volatile',
        'BooleanField':'descriptor', 'ByteField':'descriptor', 'CharField':'descriptor',
        'ShortField':'descriptor', 'LongField':'descriptor', 'FloatField':'descriptor',
        'DoubleField':'descriptor', 'ArrayRef':'descriptor',
        'StringRef':'fuera del JAR',
    }
    for name, reason in cases.items():
        rejected(jar,name,h,reason)
    rejected(jar, 'Valid', '0'*64, 'hash del JAR')
    rejected(jar, 'Absent', h, 'ausente')
    missing=d/'missing.jar'
    with zipfile.ZipFile(jar) as zin, zipfile.ZipFile(missing,'w') as zout:
        for info in zin.infolist():
            if not info.filename.endswith('/Target.class'):
                zout.writestr(info, zin.read(info))
    rejected(missing, 'MissingTarget', digest(missing), 'ausente')
    dup=d/'dup.jar'
    dup.write_bytes(jar.read_bytes())
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(dup,'a') as z:
            z.writestr('net/minecraft/layouttest/Valid.class', b'bad')
    rejected(dup, 'Valid', digest(dup), 'duplicadas')
    print(f'OK: {len(cases)+4} rechazos, herencia con prefijo, ejecución anotada, layouts cíclicos; '
          'classfiles javac sintéticos; no Main')
