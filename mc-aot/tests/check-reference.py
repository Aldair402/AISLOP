#!/usr/bin/env python3
"""Comprobación de referencia sintética y rechazo de formas fuera del subconjunto."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class Good {private String value; Good(String x){value=x;} public String get(){return value;} public int unimplemented(){return 3;} }
class WrongField {Object value; WrongField(String x){value=x;} public String get(){return (String)value;} }
class TwoFields {String one,two; TwoFields(String x){one=x;} public String get(){return one;} }
class StaticInit {String value; static { System.err.print(""); } StaticInit(String x){value=x;} public String get(){return value;} }
class Parent { Parent(){} }
class Child extends Parent {String value; Child(String x){value=x;} public String get(){return value;} }
class DifferentReturn {String value; DifferentReturn(String x){value=x;} public Object get(){return value;} }
public class RefCases {}
'''
with tempfile.TemporaryDirectory(prefix='mc-ref-guards-') as tmp:
 d=pathlib.Path(tmp);(d/'RefCases.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RefCases.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','reference-demo',str(d/'fixture.jar')]
 def compile(name):return subprocess.run(base+[f'net/minecraft/test/{name}','get',str(d/name)],text=True,capture_output=True)
 good=compile('Good')
 if good.returncode:raise RuntimeError(good.stderr)
 cmd=['string','same','string','same','new','0','get','2','eq','0','3','eq','1','3','null','new','4','get','5','eq','4','6']
 p=subprocess.run([str(d/'Good'),*cmd],text=True,capture_output=True,check=True)
 if p.stdout.splitlines()!=['0','1','2','3','1','0','4','5','6','1']:raise AssertionError(p.stdout)
 for name in ('WrongField','TwoFields','StaticInit','Child','DifferentReturn'):
  r=compile(name)
  if r.returncode==0 or (d/name).exists():raise AssertionError((name,r.stderr))
 bad=subprocess.run([str(d/'Good'),'string','x','new','0','new','1'],text=True,capture_output=True)
 if bad.returncode==0 or 'String' not in bad.stderr:raise AssertionError('no se rechazó referencia de tipo incorrecto')
 print('OK: identidad, null y tipo; 5 formas de clase no soportadas rechazadas')
