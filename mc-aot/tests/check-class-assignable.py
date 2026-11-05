#!/usr/bin/env python3
"""Class.isAssignableFrom sobre el grafo cerrado de clases e interfaces."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;interface IA {} interface IB extends IA {} class Parent implements IB {} class Child extends Parent {} class Other {}
public class AssignableDemo{public static int run(int n){try{switch(n){case 0:return Parent.class.isAssignableFrom(Child.class)?1:0;case 1:return Child.class.isAssignableFrom(Parent.class)?0:2;case 2:return IA.class.isAssignableFrom(Child.class)?3:0;case 3:return IA.class.isAssignableFrom(IB.class)?4:0;case 4:return IB.class.isAssignableFrom(IA.class)?0:5;case 5:return Object.class.isAssignableFrom(Child.class)?6:0;case 6:return Parent.class.isAssignableFrom(Other.class)?0:7;case 7:return String.class.isAssignableFrom(String.class)?8:0;case 8:return Object.class.isAssignableFrom(String.class)?9:0;case 9:Class<?>c=null;return c.isAssignableFrom(Child.class)?0:1;case 10:return Parent.class.isAssignableFrom(null)?0:1;default:return 99;}}catch(NullPointerException e){return 101;}}}'''
driver='''import net.minecraft.test.AssignableDemo;public class AssignDriver{public static void main(String[]a){for(String s:a)System.out.println(AssignableDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-assignable-') as t:
 d=pathlib.Path(t);(d/'AssignableDemo.java').write_text(source);(d/'AssignDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'AssignableDemo.java'),str(d/'AssignDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/AssignableDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=[str(n) for n in range(11)]*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'AssignDriver',*seq],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} resultados Java para isAssignableFrom, herencia, interfaces y null')
