#!/usr/bin/env python3
"""Class.asSubclass uses the registered hierarchy, returns identity and preserves failure message."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;interface IA {} interface IB extends IA {} class Parent implements IB {} class Child extends Parent {} class Other {}
public class SubclassDemo {public static int unsupported(int n){return java.util.ArrayList.class.asSubclass(Parent.class)==null?0:1;}public static int run(int n){try{Class<?> a,b;switch(n){case 0:a=Child.class;b=Parent.class;break;case 1:a=Child.class;b=IA.class;break;case 2:a=Parent.class;b=Child.class;break;case 3:a=IA.class;b=IB.class;break;case 4:a=Other.class;b=IA.class;break;case 5:a=String.class;b=Parent.class;break;case 6:a=Object.class;b=Parent.class;break;case 7:a=null;b=Parent.class;break;case 8:a=Child.class;b=null;break;case 9:a=IB.class;b=IA.class;break;case 10:a=Other.class;b=Object.class;break;default:return 42;}return a.asSubclass(b)==a?1:0;}catch(NullPointerException e){return 2;}catch(ClassCastException e){String m=e.getMessage();return m.equals("class net.minecraft.test.Parent")?3:m.equals("interface net.minecraft.test.IA")?4:m.equals("class net.minecraft.test.Other")?5:m.equals("class java.lang.String")?6:m.equals("class java.lang.Object")?7:99;}}}'''
driver='''import net.minecraft.test.SubclassDemo;public class Driver{public static void main(String[]a){for(String s:a)System.out.println(SubclassDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-subclass-') as t:
 d=pathlib.Path(t);(d/'SubclassDemo.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SubclassDemo.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SubclassDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=[str(n) for n in range(12)]*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*seq],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SubclassDemo',str(d/'native-guard'),'unsupported','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'native-guard'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Class.asSubclass: tipo JDK no modelado' not in p.stderr:raise AssertionError((p.returncode,p.stdout,p.stderr))
 print(f'OK: {len(seq)} resultados Class.asSubclass, identidad, mensajes, herencia e interfaces; tipo JDK desconocido aborta')
