#!/usr/bin/env python3
"""Math.min/max F/D: diferencial con Java, incluyendo NaN y ceros firmados."""
import os
import pathlib
import random
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
compiler = root / 'target/debug/mc-aot'
source = '''package net.minecraft.test;
public class MinMax {
  public static int f(int a, int b, int op) {
    float x=Float.intBitsToFloat(a), y=Float.intBitsToFloat(b);
    return Float.floatToIntBits(op==0 ? Math.min(x,y) : Math.max(x,y));
  }
  public static long d(long a, long b, int op) {
    double x=Double.longBitsToDouble(a), y=Double.longBitsToDouble(b);
    return Double.doubleToLongBits(op==0 ? Math.min(x,y) : Math.max(x,y));
  }
}'''
driver = '''import net.minecraft.test.MinMax;
public class Oracle {
  public static void main(String[] args) {
    for (int i=0; i<args.length; i+=4) {
      int op=Integer.parseInt(args[i+3]);
      if (args[i].equals("f"))
        System.out.println(MinMax.f(Integer.parseInt(args[i+1]),Integer.parseInt(args[i+2]),op));
      else System.out.println(MinMax.d(Long.parseLong(args[i+1]),Long.parseLong(args[i+2]),op));
    }
  }
}'''

def run(args, **kw):
    return subprocess.run([str(x) for x in args], text=True, capture_output=True, timeout=180, **kw)

def signed(n, bits):
    return n - (1 << bits) if n & (1 << (bits - 1)) else n

with tempfile.TemporaryDirectory(prefix='mc-minmax-') as tmp:
    d = pathlib.Path(tmp)
    (d / 'MinMax.java').write_text(source)
    (d / 'Oracle.java').write_text(driver)
    result = run([jdk / 'javac', '-d', d, d / 'MinMax.java', d / 'Oracle.java'])
    assert result.returncode == 0, result.stderr
    jar = d / 'fixture.jar'
    result = run([jdk / 'jar', 'cf', jar, '-C', d, 'net'])
    assert result.returncode == 0, result.stderr
    binary = d / 'native'
    result = run([compiler, 'multi-static-demo', jar, 'net/minecraft/test/MinMax', binary,
                  'f', '(III)I', 'd', '(JJI)J'])
    assert result.returncode == 0, result.stderr
    rng = random.Random(888)
    floats = [0, 0x80000000, 1, 0x80000001, 0x3f800000, 0xbf800000,
              0x7f800000, 0xff800000, 0x7fc00000, 0xffc00001, 0x7f800001]
    doubles = [0, 0x8000000000000000, 1, 0x8000000000000001,
               0x3ff0000000000000, 0xbff0000000000000, 0x7ff0000000000000,
               0xfff0000000000000, 0x7ff8000000000000, 0xfff8000000000001, 0x7ff0000000000001]
    floats += [rng.getrandbits(32) for _ in range(8)]
    doubles += [rng.getrandbits(64) for _ in range(8)]
    cases = [(label, str(signed(a, bits)), str(signed(b, bits)), str(op))
             for label, values, bits in [('f', floats, 32), ('d', doubles, 64)]
             for a in values for b in values for op in (0, 1)]
    # Evitar ARG_MAX y contrastar por lotes. El binario no tiene Java en PATH.
    for start in range(0, len(cases), 150):
        batch = cases[start:start+150]
        java = run([jdk / 'java', '-cp', d, 'Oracle', *[x for row in batch for x in row]])
        native = run([binary, *[x for label,a,b,op in batch for x in ('0' if label == 'f' else '1', a, b, op)]],
                     env=dict(os.environ, PATH='/nonexistent'))
        assert java.returncode == native.returncode == 0, (java.stderr, native.stderr)
        expected, got = java.stdout.splitlines(), native.stdout.splitlines()
        assert len(expected) == len(got) == len(batch), (len(expected), len(got), len(batch))
        for case, a, b in zip(batch, expected, got):
            assert a == b, (case, a, b)
    print(f'OK: {len(cases)} comparaciones Math.min/max float/double contra Java; NaN, ±0, infinitos y valores aleatorios; sin JVM')
