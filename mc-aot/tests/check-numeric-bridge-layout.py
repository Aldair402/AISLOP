#!/usr/bin/env python3
"""Pruebas aisladas del validador A-02; no ejercitan Main ni certifican clases."""
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
class NonFinal { int x; }
interface Interface {}
interface Tag {}
final class HasInterface implements Tag { int x; }
class Parent {}
final class Child extends Parent {}
final class StaticField { static final int X=1; }
final class Initializer { static { System.out.println("init"); } }
final class FinalInt { final int x=1; }
final class VolatileInt { volatile int x; }
final class BooleanField { boolean x; }
final class ByteField { byte x; }
final class CharField { char x; }
final class ShortField { short x; }
final class LongField { long x; }
final class FloatField { float x; }
final class DoubleField { double x; }
final class MutableRef { Target x; }
final class VolatileRef { volatile Target x; }
final class ArrayRef { final int[] x = null; }
final class StringRef { final String x = null; }
class ParentTarget { int y; }
class ParentSub extends ParentTarget {}
final class InvalidTarget { final ParentTarget x = null; }
final class MissingTarget { final Target x = null; }
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

with tempfile.TemporaryDirectory(prefix='mc-bridge-layout-') as tmp:
    d=pathlib.Path(tmp)
    (d/'Classes.java').write_text(source)
    subprocess.run([str(java/'javac'), '-d', str(d), str(d/'Classes.java')], check=True)
    jar=d/'classes.jar'
    with zipfile.ZipFile(jar, 'w') as z:
        for p in sorted((d/'net').rglob('*.class')):
            z.write(p, p.relative_to(d).as_posix())
    h=digest(jar)
    result=verify(jar, 'net/minecraft/layouttest/Valid', compiler, h)
    assert [x['class'].split('/')[-1] for x in result['classes']] == ['Valid', 'Target']
    assert [[x['kind'] for x in c['fields']] for c in result['classes']] == [['int','ref'],['int','ref']]
    assert all(len(c['sha256']) == 64 for c in result['classes'])
    rust=rust_layouts(result)
    assert 'static LAYOUT_0:' in rust and 'static LAYOUT_1:' in rust
    assert 'NumericGraphSlot::Ref("net/minecraft/layouttest/Target")' in rust
    empty=verify(jar, 'net/minecraft/layouttest/Empty', compiler, h)
    assert empty['classes'][0]['fields'] == []
    reverse=verify(jar, 'net/minecraft/layouttest/Reverse', compiler, h)
    assert [x['kind'] for x in reverse['classes'][0]['fields']] == ['ref','int']
    assert 'fields:&[NumericGraphSlot::Ref("net/minecraft/layouttest/Reverse"),NumericGraphSlot::Int]' in rust_layouts(reverse)
    try:
        verify(jar, 'net/minecraft/layouttest/MutableRef2', compiler, h)
    except ValueError as e:
        assert 'referencia no final' in str(e), e
    else:
        raise AssertionError('aceptó referencia mutable sin opt-in')
    mutable=verify(jar, 'net/minecraft/layouttest/MutableRef2', compiler, h, True)
    assert [x['kind'] for x in mutable['classes'][0]['fields']]==['mutref','int']
    assert 'NumericGraphSlot::MutRef("net/minecraft/layouttest/MutableRef2")' in rust_layouts(mutable)
    rejected_mutable=verify(jar, 'net/minecraft/layouttest/MutableRef', compiler, h, True)
    assert [x['kind'] for x in rejected_mutable['classes'][0]['fields']]==['mutref']
    # Tipo cerrado: `final` ya no es la única forma. Una clase sin subclases en el
    # JAR no puede recibir instancias de un subtipo, así que su layout es exacto;
    # una que sí las tiene sigue rechazándose.
    closed=verify(jar, 'net/minecraft/layouttest/NonFinal', compiler, h)
    assert [f['kind'] for f in closed['classes'][0]['fields']]==['int']
    assert closed['classes'][0]['closed_by']=='no-subclasses', closed['classes'][0]
    assert result['classes'][0]['closed_by']=='final', result['classes'][0]
    cases={
        'ParentTarget':'cerrada', 'Interface':'abstracta',
        'HasInterface':'interfaces no soportadas', 'Child':'superclase incompatible', 'StaticField':'estáticos',
        'Initializer':'inicializador', 'FinalInt':'int final',
        'VolatileInt':'volatile', 'VolatileRef':'volatile',
        'BooleanField':'descriptor', 'ByteField':'descriptor', 'CharField':'descriptor',
        'ShortField':'descriptor', 'LongField':'descriptor', 'FloatField':'descriptor',
        'DoubleField':'descriptor',
        'ArrayRef':'descriptor', 'StringRef':'referencia fuera', 'InvalidTarget':'cerrada',
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
    mr=d/'mr.jar'
    mr.write_bytes(jar.read_bytes())
    with zipfile.ZipFile(mr,'a') as z:
        z.writestr('META-INF/versions/25/net/minecraft/layouttest/Valid.class', b'bad')
    rejected(mr, 'Valid', digest(mr), 'multi-release')
    command=[sys.executable, str(root/'tools/numeric_bridge_layout.py'), str(jar), 'net/minecraft/layouttest/Valid', '--compiler', str(compiler), '--jar-sha256', h]
    cli=subprocess.run(command, text=True, capture_output=True, check=True)
    assert 'numeric-graph-layout-v1' in cli.stdout
    bad=subprocess.run(command[:-1]+['0'*64], text=True, capture_output=True)
    assert bad.returncode != 0 and not bad.stdout and 'hash del JAR' in bad.stderr
    print(f'OK: 2 layouts cíclicos, layout vacío, orden inverso y referencia mutable opt-in; {len(cases)+6} rechazos; classfiles javac sintéticos; no Main')
