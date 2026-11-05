#!/usr/bin/env python3
"""Comprueba que static-demo rechaza inicialización fuera de su subconjunto."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class Parent {}
class Child extends Parent {static int run(){return 1;}}
class Interfaced implements Runnable {public void run(){} static int test(){return 1;}}
class RefField {static String text="x";static int run(){return 1;}}
class VolatileField {static volatile int x;static int run(){return x;}}
class StatefulOther {static int x=2;static int get(){return x;}}
class ForeignInit {static int x=StatefulOther.get();static int run(){return x;}}
class ForeignField {static int run(){return StatefulOther.x;}}
class ObjectInit {static {Object x=new Object();}static int run(){return 1;}}
class Simple {static int x;static int run(){return x;}}
'''
with tempfile.TemporaryDirectory(prefix='mc-static-guards-') as tmp:
 d=pathlib.Path(tmp);(d/'GuardClasses.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'GuardClasses.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cases=[('Child','run','()I','sin interfaces'),('Interfaced','test','()I','sin interfaces'),('RefField','run','()I','campo estático no primitivo'),('VolatileField','run','()I','volatile'),('ForeignInit','run','()I','inicialización no soportada'),('ForeignField','run','()I','campo estático externo'),('ObjectInit','run','()I','new no soportado'),('Simple','<clinit>','()V','inicializador no invocable'),('Simple','@missing','I','campo estático no declarado')]
 for cls,name,desc,expected in cases:
  out=d/cls;p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','static-demo',str(d/'fixture.jar'),'net/minecraft/test/'+cls,str(out),name,desc],capture_output=True,text=True)
  if p.returncode==0 or expected not in p.stderr or out.exists():raise AssertionError((cls,p.returncode,p.stderr,out.exists()))
 print(f'OK: {len(cases)} formas no soportadas rechazadas (herencia, interfaces, referencias, volatile e inicializaciones externas)')
