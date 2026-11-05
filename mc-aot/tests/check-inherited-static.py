#!/usr/bin/env python3
"""Campos heredados e inicialización de superclase e interfaces contra Java."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class T {static int trace;static int mark(int n){trace=trace*10+n;return n;}}
interface Flag {int flag=T.mark(2);default int f(){return 5;}}
class Base {static int base=T.mark(1);static int shared=7;}
class Child extends Base implements Flag {static int own=T.mark(3);}
class BadBase {static int x=fail();static int fail(){int z=0;return 1/z;}}
class BadChild extends BadBase {static int child=1;}
public class InheritedStaticDemo {public static int run(int n){try{switch(n){case 0:return Child.base*10000+T.trace;case 1:return Child.own*10000+T.trace;case 2:return Child.flag*10000+T.trace;case 3:Child.shared++;return Base.shared;case 4:return T.trace;case 5:return BadChild.child;default:return 99;}}catch(ExceptionInInitializerError e){return 105;}catch(NoClassDefFoundError e){return 106;}}}
'''
driver='''import net.minecraft.test.InheritedStaticDemo;public class InheritedStaticDriver{public static void main(String[]a){for(String s:a)System.out.println(InheritedStaticDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-inherited-static-') as t:
 d=pathlib.Path(t);(d/'InheritedStaticDemo.java').write_text(source);(d/'InheritedStaticDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InheritedStaticDemo.java'),str(d/'InheritedStaticDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/InheritedStaticDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seqs=[['0','4','1','2','3','3','4','5','5'],['2','4','0','1','4'],['1','0','2','4']]
 for seq in seqs:
  java=subprocess.run([str(jdk/'java'),'-cp',str(d),'InheritedStaticDriver',*seq],capture_output=True,text=True,check=True).stdout
  native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
  if java!=native:raise AssertionError((seq,java,native))
 print('OK: 19 operaciones Java de campos heredados, inicialización de superclases e interfaces y fallos de inicialización')
