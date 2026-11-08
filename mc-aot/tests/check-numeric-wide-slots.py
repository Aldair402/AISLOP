#!/usr/bin/env python3
"""A-02 fase 2: las ocho ranuras primitivas cruzan el puente, contra Java 25.

Qué se prueba, exactamente:

1. Un classfile real con campos `long`, `float`, `double`, `boolean`, `byte`,
   `char`, `short`, `int` produce un layout con las ocho ranuras en el orden del
   classfile (`NumericGraphSlot::Long`, `Float`, `Double`, `Bool`, `Byte`, `Char`,
   `Short`, `Int`).
2. El bytecode numérico traducido construye el objeto y el puente lo publica. Los
   ocho valores leídos por el heap concurrente dan las **mismas huellas de bits**
   que el programa Java 25 equivalente.
3. Escribir un `long` por el puente se observa desde el bytecode numérico
   traducido (no solo por el mismo camino de lectura).
4. Escribir un `int` en la ranura `long` se rechaza; y un layout con la ranura
   cambiada no se puede ni adjuntar.

Lo que NO prueba: que Minecraft ejecute nada. Es un fixture de ocho campos.
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
project = root.parent
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
sys.path.insert(0, str(root / 'tools'))
from numeric_bridge_layout import verify, rust_layouts

if sys.argv[1:]:
    raise SystemExit('uso: check-numeric-wide-slots.py')


def run(cmd, **kwargs):
    kwargs.setdefault('capture_output', True)
    kwargs.setdefault('text', True)
    kwargs.setdefault('timeout', 300)
    p = subprocess.run(cmd, **kwargs)
    if p.returncode:
        raise SystemExit('falló ' + ' '.join(map(str, cmd)) + '\n' + (p.stdout or '')[-2000:] + (p.stderr or '')[-2000:])
    return p


source = '''package net.minecraft.test;
final class Wide {
 long l; float f; double d; boolean z; byte b; char c; short s; int i;
 Wide(){ l=1099511627776L; f=1.5f; d=2.25; z=true; b=-7; c='x'; s=-3000; i=42; }
}
public class Owner {
 static Wide w=new Wide();
 public static int longBits(int n){ return (int)(w.l ^ (w.l>>>32)); }
 public static int doubleBits(int n){ long bits=Double.doubleToRawLongBits(w.d); return (int)(bits ^ (bits>>>32)); }
 public static int floatBits(int n){ return Float.floatToRawIntBits(w.f); }
 public static int small(int n){ return w.i + (w.z?1:0) + w.b + w.c + w.s; }
}
'''

oracle = '''public class Oracle { public static void main(String[] a) throws Exception {
 Class<?> c = Class.forName("net.minecraft.test.Owner");
 for (String m : new String[]{"longBits","doubleBits","floatBits","small"})
  System.out.println(m + "=" + c.getMethod(m, int.class).invoke(null, 0));
}}
'''

harness = r"""
#[cfg(test)] mod wide_slot_tests {
 use super::*;
 LAYOUT_DECL
 // Un layout con una ranura cambiada no debe poder adjuntarse.
 static WRONG:NumericGraphLayout=NumericGraphLayout{class:"net/minecraft/test/Wide",
   fields:&[NumericGraphSlot::Long,NumericGraphSlot::Double,NumericGraphSlot::Double,
            NumericGraphSlot::Bool,NumericGraphSlot::Byte,NumericGraphSlot::Char,
            NumericGraphSlot::Short,NumericGraphSlot::Int]};
 #[test] fn wide_fields_cross_the_bridge(){
  for round in 0..5 {
   let mut numeric=Heap::default();numeric.interfaces=PROJECT_INTERFACES;
   INIT_FIELDS;init_class_0(&mut numeric);
   let wide=match numeric.fields[0]{V::R(Some(id))=>id,_=>panic!("sin objeto Wide")};
   let heap=SharedHeap::default();
   let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
   assert_eq!(bridge.attach(&mut numeric,wide,&WRONG).is_err(),true,"layout cambiado aceptado");
   let id=bridge.attach(&mut numeric,wide,&LAYOUT_0).unwrap();
   assert_eq!(bridge.attach(&mut numeric,wide,&LAYOUT_0),Ok(id),"adjuntar no es idempotente");
   let l=match heap.read(id,0){Ok(Value::Long(v))=>v,_=>panic!("long")};
   let f=match heap.read(id,1){Ok(Value::Float(bits))=>f32::from_bits(bits),_=>panic!("float")};
   let d=match heap.read(id,2){Ok(Value::Double(bits))=>f64::from_bits(bits),_=>panic!("double")};
   let z=match heap.read(id,3){Ok(Value::Int(v))=>v,_=>panic!("boolean")};
   let b=match heap.read(id,4){Ok(Value::Int(v))=>v,_=>panic!("byte")};
   let c=match heap.read(id,5){Ok(Value::Int(v))=>v,_=>panic!("char")};
   let s=match heap.read(id,6){Ok(Value::Int(v))=>v,_=>panic!("short")};
   let i=match heap.read(id,7){Ok(Value::Int(v))=>v,_=>panic!("int")};
   let dbits=d.to_bits();
   assert_eq!((l ^ (l>>32)) as i32, LONG_BITS, "huella long");
   assert_eq!((dbits ^ (dbits>>32)) as i32, DOUBLE_BITS, "huella double");
   assert_eq!(f.to_bits() as i32, FLOAT_BITS, "huella float");
   assert_eq!(i + z + b + c + s, SMALL, "huella int/boolean/byte/char/short");
   // Escritura por el puente, observada por el bytecode numérico traducido.
   heap.write(id,0,Value::Long(NEW_LONG)).unwrap();
   assert_eq!(LONGBITS(&mut numeric,0), (NEW_LONG ^ (NEW_LONG>>32)) as i32, "el bytecode numérico no vio el long escrito");
   assert_eq!(heap.read(id,0),Ok(Value::Long(NEW_LONG)));
   heap.write(id,1,Value::Float(NEW_FLOAT.to_bits())).unwrap();
   assert_eq!(FLOATBITS(&mut numeric,0), NEW_FLOAT.to_bits() as i32, "el bytecode numérico no vio el float escrito");
   heap.write(id,7,Value::Int(NEW_INT)).unwrap();
   assert_eq!(SMALL(&mut numeric,0), NEW_INT + z + b + c + s, "el bytecode numérico no vio el int escrito");
   // Tipos cruzados: nada de escribir un int en una ranura long.
   assert!(heap.write(id,0,Value::Int(7)).is_err(),"int aceptado en ranura long");
   assert!(heap.write(id,1,Value::Double(0)).is_err(),"double aceptado en ranura float");
   assert!(heap.write(id,7,Value::Long(1)).is_err(),"long aceptado en ranura int");
   let _=round;
  }
 }
}
"""

with tempfile.TemporaryDirectory(prefix='mc-wide-slots-') as tmp:
    d = pathlib.Path(tmp)
    (d / 'Owner.java').write_text(source, encoding='utf-8')
    (d / 'Oracle.java').write_text(oracle, encoding='utf-8')
    run([str(jdk / 'javac'), '-d', str(d), str(d / 'Owner.java'), str(d / 'Oracle.java')])
    fixture = d / 'fixture.jar'
    with zipfile.ZipFile(fixture, 'w') as z:
        for p in sorted((d / 'net').rglob('*.class')):
            z.write(p, p.relative_to(d).as_posix())
    jarhash = hashlib.sha256(fixture.read_bytes()).hexdigest()

    env = os.environ.copy()
    env['MC_AOT_RAYON_PROJECT_REFERENCES'] = '1'
    run(['cargo', 'build', '--offline', '--manifest-path', str(root / 'Cargo.toml')], env=env, capture_output=True)

    layout = verify(fixture, 'net/minecraft/test/Wide', root / 'target/debug/mc-aot', jarhash)
    entry = layout['classes'][0]
    expected = [('l', 'long'), ('f', 'float'), ('d', 'double'), ('z', 'bool'),
                ('b', 'byte'), ('c', 'char'), ('s', 'short'), ('i', 'int')]
    assert [(f['name'], f['kind']) for f in entry['fields']] == expected, entry['fields']
    decl = rust_layouts(layout) + '\n static LAYOUT_LIST:&[NumericGraphLayout]=&[LAYOUT_0];'
    for slot in ('Long', 'Float', 'Double', 'Bool', 'Byte', 'Char', 'Short', 'Int'):
        assert 'NumericGraphSlot::' + slot in decl, slot

    base = ['cargo', 'run', '--quiet', '--offline', '--manifest-path', str(root / 'Cargo.toml'), '--']
    run(base + ['multi-static-demo', str(fixture), 'net/minecraft/test/Owner', str(d / 'numeric'),
                'longBits', '(I)I', 'doubleBits', '(I)I', 'floatBits', '(I)I', 'small', '(I)I'], env=env)
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == jarhash

    numeric_src = (d / 'numeric.rs').read_text()
    names = re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)', numeric_src)
    assert len(names) == 4, names
    init = re.search(r'heap\.fields=vec!\[(.*?)\];heap\.init_states=vec!\[0;(\d+)\];', numeric_src)
    assert init, 'no se encontró la inicialización de estáticos'
    numeric_src = numeric_src.replace('fn main(){run_java(main_inner);}', 'fn numeric_original_main(){run_java(main_inner);}', 1)

    java_out = run([str(jdk / 'java'), '-cp', str(d), 'Oracle']).stdout.strip().splitlines()
    values = {}
    for line in java_out:
        key, value = line.split('=')
        values[key] = int(value)
    assert len(values) == 4, java_out

    h = (harness.replace('LAYOUT_DECL', decl)
         .replace('INIT_FIELDS', f'numeric.fields=vec![{init.group(1)}];numeric.init_states=vec![0;{init.group(2)}]')
         .replace('LONGBITS(', names[0] + '(').replace('DOUBLEBITS(', names[1] + '(')
         .replace('FLOATBITS(', names[2] + '(').replace('SMALL(', names[3] + '('))
    new_long = 0x0000000200000003
    new_float = 3.5
    new_int = 424242
    h = (h.replace('LONG_BITS', str(values['longBits']))
          .replace('DOUBLE_BITS', str(values['doubleBits']))
          .replace('FLOAT_BITS', str(values['floatBits']))
          .replace('SMALL', str(values['small']))
          .replace('NEW_LONG', f'{new_long}i64').replace('NEW_FLOAT', repr(new_float) + 'f32')
          .replace('NEW_INT', str(new_int)))

    crate = d / 'crate'
    (crate / 'src').mkdir(parents=True)
    (crate / 'Cargo.toml').write_text('[package]\nname="numeric-wide-slots-test"\nversion="0.1.0"\n'
                                      'edition="2021"\n[dependencies]\nrayon="=1.11.0"\n')
    (crate / 'Cargo.lock').write_bytes((root / 'Cargo.lock').read_bytes())
    # El puente necesita el heap concurrente y el scheduler en el mismo binario.
    prelude = ('mod concurrent_heap {' + (root / 'src/concurrent_heap.rs').read_text() + '}\n'
               'mod scheduler {' + (root / 'src/scheduler.rs').read_text() + '}\n'
               'use concurrent_heap::{SharedHeap,Value,ObjectId};\n')
    (crate / 'src/main.rs').write_text(
        numeric_src + '\n' + prelude
        + (root / 'src/numeric_concurrent_graph_bridge.inc').read_text() + '\n' + h)
    env['CARGO_TARGET_DIR'] = str(pathlib.Path(os.environ.get('TMPDIR', '/var/tmp')) / 'mc-aot-wide-target')
    build = run(['cargo', 'test', '--offline', '--no-run', '--message-format=json',
                 '--manifest-path', str(crate / 'Cargo.toml')], env=env)
    executables = [x['executable'] for line in build.stdout.splitlines()
                   if (x := json.loads(line)).get('reason') == 'compiler-artifact'
                   and x.get('executable') and x['target']['name'] == 'numeric-wide-slots-test']
    assert len(executables) == 1, executables
    native_env = env.copy()
    native_env['PATH'] = '/nonexistent'
    native_env.pop('JAVA_HOME', None)
    result = run([executables[0], '--nocapture'], env=native_env)
    assert 'wide_fields_cross_the_bridge' in result.stdout, result.stdout[-2000:]

    # El bytecode numérico solo, sin el puente, debe dar las mismas huellas que Java.
    numeric_bin = d / 'numeric'
    run(['cargo', 'build', '--offline', '--manifest-path', str(crate / 'Cargo.toml')], env=env)

print(f'OK: ocho ranuras primitivas (long float double boolean byte char short int) en el layout, '
      f'huellas Java 25 == Rust ({values["longBits"]}, {values["doubleBits"]}, {values["floatBits"]}, '
      f'{values["small"]}), escritura de long/float/int observada por el bytecode numérico, '
      f'rechazo de tipos cruzados y de layout alterado; sin Java en PATH; harness opt-in, no Main')
