#!/usr/bin/env python3
"""Atributo Record: comparación estructural con reflexión Java 25, más entradas rotas."""
import os
import pathlib
import struct
import subprocess
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
jar = root.parent / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
source = r'''package net.minecraft.test;
import java.lang.annotation.*;
public class Records {
  @Target(ElementType.RECORD_COMPONENT) @Retention(RetentionPolicy.RUNTIME) public @interface Mark {}
  public record Empty() {}
  public record Mixed(@Mark int number, String name, int[] values, long wide) {}
  public static class Plain {}
}'''
driver = r'''public class Oracle {
 public static void main(String[] names) throws Exception {
  for(String name:names) {
   Class<?> c=Class.forName(name.replace('/','.'),false,Oracle.class.getClassLoader());
   var a=c.getRecordComponents();
   if(a==null){System.out.println("record\tno");continue;}
   System.out.println("record\t"+a.length);
   for(var x:a)System.out.println("component\t"+x.getName()+"\t"+x.getType().descriptorString());
  }
 }
}'''

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=180, **kwargs)

def record_attribute(data):
    """Offset de class attributes y bytes de Record en un classfile de javac."""
    b = data
    u2 = lambda p: struct.unpack_from('>H', b, p)[0]
    u4 = lambda p: struct.unpack_from('>I', b, p)[0]
    cp_count = u2(8)
    cp = {}
    pos, i = 10, 1
    while i < cp_count:
        tag = b[pos]; pos += 1
        if tag == 1:
            n = u2(pos); pos += 2
            cp[i] = b[pos:pos+n].decode('utf-8'); pos += n
        elif tag in (3,4): pos += 4
        elif tag in (5,6): pos += 8; i += 1
        elif tag in (7,8,16,19,20): pos += 2
        elif tag in (9,10,11,12,17,18): pos += 4
        elif tag == 15: pos += 3
        else: raise AssertionError(('tag', tag))
        i += 1
    pos += 6
    n = u2(pos); pos += 2 + 2*n
    for _ in range(2):
        n = u2(pos); pos += 2
        for _ in range(n):
            pos += 6
            attrs = u2(pos); pos += 2
            for _ in range(attrs):
                size = u4(pos+2); pos += 6+size
    attr_count_at = pos
    count = u2(pos); pos += 2
    for _ in range(count):
        start = pos
        name = cp[u2(pos)]; size = u4(pos+2); pos += 6+size
        if name == 'Record':
            return attr_count_at, start, pos
    raise AssertionError('fixture sin Record')

with tempfile.TemporaryDirectory(prefix='record-metadata-') as tmp:
    d = pathlib.Path(tmp)
    (d/'Records.java').write_text(source)
    (d/'Oracle.java').write_text(driver)
    javac = run([jdk/'javac', '-d', d, d/'Records.java', d/'Oracle.java'])
    assert javac.returncode == 0, javac.stderr
    fixture = d/'fixture.jar'
    packed = run([jdk/'jar', 'cf', fixture, '-C', d, 'net'])
    assert packed.returncode == 0, packed.stderr
    names = [
        'net/minecraft/test/Records$Empty', 'net/minecraft/test/Records$Mixed',
        'net/minecraft/test/Records$Plain',
        'net/minecraft/network/protocol/game/VecDelta$Stepped$DeltaStep',
        'net/minecraft/server/jsonrpc/IncomingRpcMethod$Attributes',
        'net/minecraft/server/jsonrpc/OutgoingRpcMethod$Attributes',
        'net/minecraft/util/TickThrottler',
    ]
    for name in names:
        source_jar = fixture if name.startswith('net/minecraft/test/') else jar
        java = run([jdk/'java', '-cp', f'{d}{os.pathsep}{jar}', 'Oracle', name])
        native = run([compiler, 'inspect-record', source_jar, name])
        assert java.returncode == native.returncode == 0, (name, java.stderr, native.stderr)
        assert java.stdout == native.stdout, (name, java.stdout, native.stdout)
    # Record duplicado, descriptor no válido y longitud truncada deben rechazar;
    # el parser no es un verificador completo de bytecode.
    cls = (d/'net/minecraft/test/Records$Mixed.class').read_bytes()
    count_pos, start, end = record_attribute(cls)
    duplicate = bytearray(cls)
    struct.pack_into('>H', duplicate, count_pos, struct.unpack_from('>H', cls, count_pos)[0] + 1)
    duplicate += cls[start:end]
    descriptor = bytearray(cls)
    # attribute header + component count + name_index; usar name_index como descriptor.
    descriptor[start+10:start+12] = descriptor[start+8:start+10]
    for label, broken in [('duplicate', duplicate), ('descriptor', descriptor), ('truncated', cls[:-1])]:
        badjar = d/f'{label}.jar'
        with zipfile.ZipFile(badjar, 'w') as z:
            z.writestr('net/minecraft/test/Records$Mixed.class', broken)
        result = run([compiler, 'inspect-record', badjar, 'net/minecraft/test/Records$Mixed'])
        assert result.returncode != 0, (label, result.stdout, result.stderr)
    print('OK: componentes y orden de 7 clases Java/vanilla; record vacío vs no record; duplicado, descriptor inválido y truncamiento rechazados')
