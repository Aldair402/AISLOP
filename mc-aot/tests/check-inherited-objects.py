#!/usr/bin/env python3
"""Herencia de campos, constructores y despacho cerrado: contraste Java."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
interface I {int value();} class Base implements I {int x=2;Base(){x=x+value();}public int value(){return 1;}int getBase(){return x;}int call(){return value();}}
class Child extends Base {int x=7;Child(){x=x+1;}public int value(){return x+10;}int getChild(){return x;}int fromSuper(){return super.value();}}
class Grand extends Child {int y=3;public int value(){return y+100;}int grand(){return y;}}
public class InheritedObjectsDemo {static Base a=new Base();static Base b=new Child();static Base c=new Grand();static I i=c;
 public static int run(int n){try{switch(n){case 0:return a.value()*100000+b.value()*1000+c.value();case 1:return a.getBase()*10000+b.getBase()*100+c.getBase();case 2:return b.call()*1000+c.call();case 3:return ((Child)b).getChild()*100+((Grand)c).grand();case 4:return i.value();case 5:return (a instanceof Child?1:0)+(b instanceof Base?2:0)+(c instanceof Child?4:0)+(c instanceof I?8:0);case 6:Child z=(Child)a;return z.getChild();case 7:Base nul=null;return nul.value();case 9:return ((Child)b).fromSuper()*10+((Grand)c).fromSuper();case 8:return c.getClass().getName().equals("net.minecraft.test.Grand")?8:0;default:return a.value()+b.value()+c.value();}}catch(ClassCastException e){return 106;}catch(NullPointerException e){return 107;}}
}'''
driver='''import net.minecraft.test.InheritedObjectsDemo;public class InheritedObjectsDriver{public static void main(String[]a){for(String s:a)System.out.println(InheritedObjectsDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-inherited-objects-') as t:
 d=pathlib.Path(t);(d/'InheritedObjectsDemo.java').write_text(source);(d/'InheritedObjectsDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InheritedObjectsDemo.java'),str(d/'InheritedObjectsDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/InheritedObjectsDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=[str(n) for n in range(10)]*15;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'InheritedObjectsDriver',*seq],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} operaciones Java de 3 generaciones, constructores, campos ocultos, dispatch virtual/interfaz, casts y null')
