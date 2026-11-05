#!/usr/bin/env python3
"""La ruta de objetos concretos rechaza lo que todavía no modela."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class Base {} class Sub extends Base {Sub(){}}
interface WithDefault {default int value(){return 1;}} class Implements implements WithDefault {}
class SynchronizedMethod {static synchronized int x(){return 1;}}
class UnsupportedField {double[][] value;}
class InstanceCatch {int value(int x){try{return 1/x;}catch(OutOfMemoryError e){return 0;}}}
class EqualsOverride {public boolean equals(Object o){return true;}}
class GuardSub {static int f(){new Sub();return 0;}}
class GuardInterface {static int f(){new Implements();return 0;}}
class GuardSynchronized {static int f(){return SynchronizedMethod.x();}}
class GuardField {static int f(){new UnsupportedField();return 0;}}
class GuardCatch {static int f(){return new InstanceCatch().value(1);}}
class GuardEquals {static int f(){Object a=new EqualsOverride();return a.equals(null)?1:0;}}
class GuardCast {static int f(){Object a=new Object();return ((java.math.BigInteger)a)==null?0:1;}}
'''
with tempfile.TemporaryDirectory(prefix='mc-object-guards-') as t:
 d=pathlib.Path(t);(d/'Guards.java').write_text(source);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'Guards.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cases=[('GuardSynchronized','synchronized'),('GuardField','campo estático no soportado'),('GuardCatch','tipo catch no soportado'),('GuardCast','checkcast/instanceof no soportado')]
 for cls,err in cases:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/'+cls,str(d/cls),'f','()I'],capture_output=True,text=True)
  if p.returncode==0 or err not in p.stderr or (d/cls).exists():raise AssertionError((cls,p.stderr,p.returncode))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/GuardEquals',str(d/'GuardEquals'),'f','()I'],capture_output=True,text=True)
 if p.returncode:raise AssertionError(('GuardEquals compile',p.stderr))
 p=subprocess.run([str(d/'GuardEquals'),'0'],capture_output=True,text=True)
 if p.returncode==0 or 'Object.equals: receptor fuera del perfil' not in p.stderr:raise AssertionError(('GuardEquals runtime',p.returncode,p.stderr))
 print(f'OK: {len(cases)} guardas de compilación y Object.equals de proyecto aborta al ejecutar')
