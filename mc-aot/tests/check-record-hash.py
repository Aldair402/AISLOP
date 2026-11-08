#!/usr/bin/env python3
"""ObjectMethods.hashCode acotado: Java 25 vs nativo con records integrales."""
import os
import pathlib
import random
import subprocess
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
official = root.parent / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
source = '''package net.minecraft.test;
import net.minecraft.network.protocol.game.VecDelta.Stepped.DeltaStep;
public class RecordsHash {
  public record Mixed(int i, long l, boolean z, short s, char c, byte b) {}
  public record Empty() {}
  public record Decimal(float x) {}
  public static int mixed(int i,long l,int z,int s,int c,int b) {return new Mixed(i,l,z!=0,(short)s,(char)c,(byte)b).hashCode();}
  public static int empty() {return new Empty().hashCode();}
  public static int decimal(int n) {return new Decimal(Float.intBitsToFloat(n)).hashCode();}
  public static int equal(int a,int b) {return new Mixed(a,0L,false,(short)0,(char)0,(byte)0).equals(new Mixed(b,0L,false,(short)0,(char)0,(byte)0))?1:0;}
  public static int text(int a) {return new Mixed(a,0L,false,(short)0,(char)0,(byte)0).toString().length();}
  public static int vanilla(int x,int y,int z,int ticks) {return new DeltaStep((short)x,(short)y,(short)z,ticks).hashCode();}
}'''
driver = '''import net.minecraft.test.RecordsHash;
public class Oracle {
 public static void main(String[] args) {
  for(int i=0;i<args.length;){
   int op=Integer.parseInt(args[i++]);
   if(op==0) System.out.println(RecordsHash.mixed(Integer.parseInt(args[i++]),Long.parseLong(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++])));
   else if(op==1) System.out.println(RecordsHash.empty());
   else System.out.println(RecordsHash.vanilla(Integer.parseInt(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++])));
  }
 }
}'''
def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=180, **kwargs)

with tempfile.TemporaryDirectory(prefix='record-hash-') as tmp:
    d = pathlib.Path(tmp)
    (d/'RecordsHash.java').write_text(source)
    (d/'Oracle.java').write_text(driver)
    result = run([jdk/'javac','-cp',official,'-d',d,d/'RecordsHash.java',d/'Oracle.java'])
    assert result.returncode == 0, result.stderr
    fixture = d/'fixture.jar'
    with zipfile.ZipFile(fixture,'w') as out:
        for path in (d/'net').rglob('*.class'):
            out.write(path, path.relative_to(d).as_posix())
        target = 'net/minecraft/network/protocol/game/VecDelta$Stepped$DeltaStep.class'
        with zipfile.ZipFile(official) as src:
            out.writestr(target,src.read(target))
    binary = d/'native'
    build = run([compiler,'multi-static-demo',fixture,'net/minecraft/test/RecordsHash',binary,
                 'mixed','(IJIIII)I','empty','()I','vanilla','(IIII)I'])
    assert build.returncode == 0, build.stderr
    rng = random.Random(20261108)
    cases = [('1',), ('0','0','0','0','0','0','0'),
             ('0','-2147483648','-9223372036854775808','1','-32768','65535','-128'),
             ('2','-32768','32767','-1','2147483647')]
    for i in range(100):
        if i%2:
            cases.append(('0',str(rng.randint(-2147483648,2147483647)),str(rng.randint(-9223372036854775808,9223372036854775807)),str(rng.randint(0,1)),str(rng.randint(-32768,32767)),str(rng.randint(0,65535)),str(rng.randint(-128,127))))
        else:
            cases.append(('2',*[str(rng.randint(-2147483648,2147483647)) for _ in range(4)]))
    args = [x for c in cases for x in c]
    java = run([jdk/'java','-cp',f'{d}{os.pathsep}{official}','Oracle',*args])
    native = run([binary,*args],env=dict(os.environ,PATH='/nonexistent'))
    assert java.returncode == native.returncode == 0, (java.stderr,native.stderr)
    assert len(java.stdout.splitlines()) == len(cases), (len(cases),java.stdout)
    assert java.stdout == native.stdout, (java.stdout,native.stdout)
    for name, descriptor, error in [('decimal','(I)I','ObjectMethods.hashCode: tipo no soportado: F')]:
        target = d/f'reject-{name}'
        rejected = run([compiler,'multi-static-demo',fixture,'net/minecraft/test/RecordsHash',target,name,descriptor])
        assert rejected.returncode != 0 and error in rejected.stderr and not target.exists(), (name,rejected.stderr)
    # Modificar nombres del bootstrap sin cambiar tamaño: hay que comprobar los
    # argumentos del sitio, no aceptar cualquier invokedynamic con ese propietario.
    tampered = d/'tampered.jar'
    with zipfile.ZipFile(fixture) as inp, zipfile.ZipFile(tampered,'w') as out:
        for entry in inp.infolist():
            raw = inp.read(entry.filename)
            if entry.filename == 'net/minecraft/test/RecordsHash$Mixed.class':
                assert raw.count(b'i;l;z;s;c;b') == 1
                raw = raw.replace(b'i;l;z;s;c;b', b'X;l;z;s;c;b', 1)
            out.writestr(entry.filename, raw)
    bad = d/'bad-bootstrap'
    rejected = run([compiler,'multi-static-demo',tampered,'net/minecraft/test/RecordsHash',bad,'mixed','(IJIIII)I'])
    assert rejected.returncode != 0 and 'nombres no coinciden con Record' in rejected.stderr and not bad.exists(), rejected.stderr
    # El mismo bootstrap en un cuerpo modificado no es el wrapper estándar.
    oddjar=d/'odd-wrapper.jar'
    with zipfile.ZipFile(fixture) as inp, zipfile.ZipFile(oddjar,'w') as out:
        for entry in inp.infolist():
            raw=inp.read(entry.filename)
            if entry.filename=='net/minecraft/test/RecordsHash$Mixed.class':
                found=[i for i in range(len(raw)-7) if raw[i:i+2]==b'\x2a\xba' and raw[i+4:i+7]==b'\x00\x00\xac']
                assert len(found)==1, found
                altered=bytearray(raw); altered[found[0]]=0x01; raw=bytes(altered)
            out.writestr(entry.filename,raw)
    bad=d/'bad-wrapper'
    rejected=run([compiler,'multi-static-demo',oddjar,'net/minecraft/test/RecordsHash',bad,'mixed','(IJIIII)I'])
    assert rejected.returncode!=0 and 'cuerpo no es el wrapper estándar' in rejected.stderr and not bad.exists(), rejected.stderr
    print(f'OK: {len(cases)} hashCode de records (vacío, primitivos, DeltaStep vanilla); Java 25 == nativo sin JVM; guardas de tipo, operaciones y bootstrap')
