#!/usr/bin/env python3
"""Pruebas de objeto/constructor/campo en una clase de prueba y rechazos explícitos."""
import os, pathlib, random, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
interface Thing { int get(); default int plus(){return get()+1;} }
interface Other { default int plus(){return 1;} }
class SmallBox implements Thing {
  private int x;
  SmallBox(int x) { this.x=x; }
  public int get() { return x; }
  public int doubled() { return x*2; }
  public int triple() { return x+x+x; }
}
class BadReference { String field; BadReference(int a) {} public int get(){return 0;} }
class StaticField { static int x; StaticField(int a) {} public int get(){return 0;} }
class Locked { Locked(int a) {} public synchronized int get(){return 0;} }
class Parent { Parent() {} }
class Child extends Parent { Child(int a) {} public int get(){return 0;} }
public class ObjectCases {
  public static void main(String[] args) throws Exception {
    var in=new java.io.BufferedReader(new java.io.InputStreamReader(System.in));
    for(String line;(line=in.readLine())!=null;) {
      var b=new SmallBox(Integer.parseInt(line));
      System.out.println(b.get()+","+b.plus()+","+b.doubled()+","+b.triple()+","+b.get());
    }
  }
}'''
with tempfile.TemporaryDirectory(prefix='mc-object-tests-') as temp:
 d=pathlib.Path(temp);(d/'ObjectCases.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ObjectCases.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','object-demo',str(d/'fixture.jar')]
 def compile_obj(name, extra=None, output=None):
  return subprocess.run(base+[f'net/minecraft/test/{name}',str(d/(output or name)),*(extra or [])],capture_output=True,text=True)
 result=compile_obj('SmallBox',['--default','net/minecraft/test/Thing','plus'])
 if result.returncode:raise RuntimeError(result.stderr)
 rng=random.Random(7);numbers=[-2147483648,-1073741824,-1,0,1,1073741823,2147483647]
 numbers += [rng.randint(-2147483648,2147483647) for _ in range(100)]
 result=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar'),'net.minecraft.test.ObjectCases'],input=''.join(f'{x}\n' for x in numbers),capture_output=True,text=True,check=True)
 lines=result.stdout.splitlines()
 if len(lines)!=len(numbers):raise AssertionError('referencia incompleta')
 for n,expected in zip(numbers,lines):
  p=subprocess.run([str(d/'SmallBox'),str(n),'get','plus','doubled','triple','get'],capture_output=True,text=True,check=True)
  actual=','.join(p.stdout.splitlines())
  if actual!=expected:raise AssertionError((n,actual,expected))
 for name,label in [('BadReference','no int'),('StaticField','static'),('Locked','synchronized'),('Child','herencia')]:
  r=compile_obj(name)
  if r.returncode==0 or label not in r.stderr or (d/name).exists():raise AssertionError((name,r.stderr))
 for iface,method,label in [('net/minecraft/test/Other','plus','directamente'),('net/minecraft/test/Thing','get','implementa el método'),('net/minecraft/test/Thing','missing','no encontrado')]:
  r=compile_obj('SmallBox',['--default',iface,method],'reject-default')
  if r.returncode==0 or label not in r.stderr or (d/'reject-default').exists():raise AssertionError((iface,method,r.stderr))
 print(f'OK: {len(numbers)} objetos sintéticos y {len(numbers)*5} llamadas; 7 casos no admitidos rechazados')
