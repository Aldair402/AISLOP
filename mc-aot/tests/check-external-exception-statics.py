#!/usr/bin/env python3
"""Inicialización estática de subclases de Exception sin fingir sus instancias."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class Ex extends Exception {static int value=State.bump();Ex(){super();}}
class Sub extends Ex {static int value2=State.bump();}
class State {static int count;static int bump(){return ++count;}}
public class ExStaticDemo {
 public static int run(int n){switch(n%4){case 0:return Ex.value;case 1:return Sub.value2;case 2:return State.count;default:return Sub.value;}}
 public static int bad(){return new Ex()==null?1:2;}
}'''
driver='''import net.minecraft.test.ExStaticDemo;public class ExDriver{public static void main(String[]a){for(String s:a)System.out.println(ExStaticDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-ex-static-') as t:
 d=pathlib.Path(t);(d/'ExStaticDemo.java').write_text(source);(d/'ExDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ExStaticDemo.java'),str(d/'ExDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ExStaticDemo']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 for vals in ([0,2,1,3,2],[1,0,2,3],[2,3,2,1,2]):
  j=subprocess.run([str(jdk/'java'),'-cp',str(d),'ExDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
  a=subprocess.run([str(d/'native'),*[x for n in vals for x in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
  if j!=a:raise AssertionError((vals,j,a))
 p=subprocess.run(base+[str(d/'bad'),'bad','()I'],capture_output=True,text=True)
 if p.returncode==0 or 'excepción' not in p.stderr or 'no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 14 lecturas estáticas de excepciones heredadas; instancias rechazadas')
