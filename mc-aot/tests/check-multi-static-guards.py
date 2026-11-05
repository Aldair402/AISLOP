#!/usr/bin/env python3
"""Rechazos seguros del experimento de inicialización multiclase."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class Base {} class Inherited extends Base {static int get(){return 1;}}
interface HasDefault {default int value(){return 1;}} class InterfaceType implements HasDefault {static int get(){return 1;}}
class RefStatic {static float[][] x;static int get(){return 1;}}
class SynchronizedStatic {static synchronized int get(){return 1;}}
class External {static int get(){return System.in.available();}}
class WithCatch {static int get(int n){try{return 10/n;}catch(OutOfMemoryError e){return 1;}}}
class BadOther {static float[][] name;static int get(){return 2;}}
class CallsBad {static int get(){return BadOther.get();}}
class DivideInit {static int x=1/zero();static int zero(){return 0;}static int get(){return x;}}
'''.replace('class External {static int get(){return System.in.available();}}','class External {static int get(){return (int)java.lang.System.nanoTime();}}')
with tempfile.TemporaryDirectory(prefix='mc-multi-static-guards-') as tmp:
 d=pathlib.Path(tmp);(d/'GuardClasses.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'GuardClasses.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cases=[('RefStatic','()I','campo estático no soportado'),('SynchronizedStatic','()I','synchronized'),('External','()I','invokestatic no soportado'),('WithCatch','(I)I','tipo catch no soportado'),('CallsBad','()I','campo estático no soportado')]
 for cls,desc,err in cases:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/'+cls,str(d/cls),'get',desc],capture_output=True,text=True)
  if p.returncode==0 or err not in p.stderr or (d/cls).exists():raise AssertionError((cls,p.returncode,p.stderr))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DivideInit',str(d/'divide'),'get','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 q=subprocess.run([str(d/'divide'),'0'],capture_output=True,text=True)
 if q.returncode!=2 or 'ExceptionInInitializerError' not in q.stderr:raise AssertionError(('fallo init',q.returncode,q.stderr))
 print(f'OK: {len(cases)} formas inseguras rechazadas; falla de <clinit> termina el proceso con ExceptionInInitializerError')
