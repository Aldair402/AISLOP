#!/usr/bin/env python3
"""Identidad restringida de ClassLoader; no simula ServiceLoader ni reflexión."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class ClassLoaderDemo {
 static int count=1;static int bump(){return ++count;}static Class<?> unknown;
 public static int check(){ClassLoader a=ClassLoaderDemo.class.getClassLoader();return (a!=null?1:0)+(a==Mark.class.getClassLoader()?2:0)+(a==Other.class.getClassLoader()?4:0)+(String.class.getClassLoader()==null?8:0)+(Class.class.getClass()==Class.class?16:0)+(Class.class.getClassLoader()==null?32:0)+(Class.class.getName().equals("java.lang.Class")?64:0)+count*100;}
 public static int missing(){return unknown.getClassLoader()==null?1:0;}
}
interface Mark {int x=ClassLoaderDemo.bump();}class Other {}
'''
driver='''import net.minecraft.test.ClassLoaderDemo;public class ClassLoaderDriver{public static void main(String[] x){System.out.println(ClassLoaderDemo.check());System.out.println(ClassLoaderDemo.check());try{ClassLoaderDemo.missing();}catch(NullPointerException e){System.out.println("NullPointerException");}}}'''
with tempfile.TemporaryDirectory(prefix='mc-classloader-') as t:
 d=pathlib.Path(t);(d/'ClassLoaderDemo.java').write_text(source);(d/'ClassLoaderDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ClassLoaderDemo.java'),str(d/'ClassLoaderDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ClassLoaderDemo',str(d/'native'),'check','()I','missing','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ClassLoaderDriver'],capture_output=True,text=True,check=True).stdout.splitlines()
 p=subprocess.run([str(d/'native'),'0','0','1'],capture_output=True,text=True)
 if java!=['227','227','NullPointerException'] or p.stdout.splitlines()!=java[:-1] or p.returncode!=2 or 'NullPointerException' not in p.stderr:raise AssertionError((java,p.stdout,p.stderr,p.returncode))
 print('OK: identidad de loader de clases/interfaz y bootstrap Java coincide; literal de interfaz no inicializa; null coincide')
