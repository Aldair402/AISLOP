#!/usr/bin/env python3
"""Comprobación aislada de flujo, llamadas, enteros y rechazo de funciones no implementadas."""
import os
import pathlib
import random
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
source = '''package net.minecraft.test;
public class Fixture {
  public static int square(int x) { return x * x; }
  public static int choose(int x) { if (x < 0) return square(x); return x + 1; }
  public static int recurse(int x) { if (x == 0) return 0; return recurse(x - 1); }
  public static int object(int x) { return Integer.valueOf(x).intValue(); }
  public static synchronized int locked(int x) { return x; }
  public static int divide(int a,int b) { return a / b; }
  public static int remainder(int a,int b) { return a % b; }
  public static int narrow(int a) { return (byte)a + (char)a + (short)a; }
  public static boolean isEven(int a) { return (a & 1) == 0; }
  public static int chooseBoolean(int a) { return isEven(a) ? 7 : 9; }
  public static byte asByte(int a) { return (byte) a; }
  public static char asChar(int a) { return (char) a; }
  public static short asShort(int a) { return (short) a; }
  private static String result(java.util.function.IntSupplier x) {
    try { return Integer.toString(x.getAsInt()); } catch (ArithmeticException e) { return "ERR_ARITHMETIC"; }
  }
  public static void main(String[] args) throws Exception {
    var in = new java.io.BufferedReader(new java.io.InputStreamReader(System.in));
    for (String s; (s=in.readLine()) != null;) {
      var p=s.split(","); int a=Integer.parseInt(p[0]), b=Integer.parseInt(p[1]);
      System.out.println(choose(a)+","+result(()->divide(a,b))+","+result(()->remainder(a,b))+","+narrow(a)+","+(isEven(a)?1:0)+","+chooseBoolean(a)+","+asByte(a)+","+(int)asChar(a)+","+asShort(a));
    }
  }
}'''
with tempfile.TemporaryDirectory(prefix='mc-guards-') as temp:
    d = pathlib.Path(temp); (d/'Fixture.java').write_text(source)
    subprocess.run([str(jdk/'javac'), '-d', str(d), str(d/'Fixture.java')], check=True)
    subprocess.run([str(jdk/'jar'), 'cf', str(d/'fixture.jar'), '-C', str(d), 'net'], check=True)
    base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'fixture.jar'),'net/minecraft/test/Fixture']
    def compile_method(method, desc):
        return subprocess.run(base+[method,desc,str(d/method)], text=True, capture_output=True)
    for method, desc in [('choose','(I)I'),('divide','(II)I'),('remainder','(II)I'),('narrow','(I)I'),('isEven','(I)Z'),('chooseBoolean','(I)I'),('asByte','(I)B'),('asChar','(I)C'),('asShort','(I)S')]:
        result=compile_method(method,desc)
        if result.returncode: raise RuntimeError(result.stderr)
    rng=random.Random(123)
    values=[-2147483648,-50000,-2,-1,0,1,127,128,255,256,32767,32768,65535,65536,2147483647]
    values += [rng.randint(-2147483648,2147483647) for _ in range(50)]
    pairs=[(a,values[(i*13+3)%len(values)]) for i,a in enumerate(values)]
    pairs += [(-2147483648,-1),(1,0),(0,0),(-7,3),(7,-3)]
    ref=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar'),'net.minecraft.test.Fixture'], input=''.join(f'{a},{b}\n' for a,b in pairs), capture_output=True,text=True,check=True).stdout.splitlines()
    if len(ref)!=len(pairs): raise AssertionError('salida incompleta JVM')
    for (a,b),line in zip(pairs,ref):
        want=line.split(',')
        for (method,arguments),expected in zip([('choose',[a]),('divide',[a,b]),('remainder',[a,b]),('narrow',[a]),('isEven',[a]),('chooseBoolean',[a]),('asByte',[a]),('asChar',[a]),('asShort',[a])],want):
            result=subprocess.run([str(d/method),*map(str,arguments)],capture_output=True,text=True)
            if expected == 'ERR_ARITHMETIC':
                if result.returncode == 0 or 'ArithmeticException' not in result.stderr:
                    raise AssertionError((method,arguments,result,expected))
            elif result.returncode != 0 or result.stdout.strip() != expected:
                raise AssertionError((method,arguments,result,expected))
    for method, label in [('recurse','recursión'),('object','no soportado'),('locked','synchronized')]:
        result=compile_method(method,'(I)I')
        if result.returncode==0 or label not in result.stderr or (d/method).exists():
            raise AssertionError((method,result.returncode,result.stderr))
    print(f'OK: {len(pairs)*9} resultados; recursión, objetos y synchronized rechazados; errores aritméticos por categoría')
