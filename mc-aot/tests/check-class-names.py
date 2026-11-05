#!/usr/bin/env python3
"""Object.getClass y Class.getName/getClassLoader con tipos acotados."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ClassNameDemo {
 interface I{}static final class X implements I{}static Object x=new X(),nil=null;static I i=(I)x;
 public static int run(int n){try{switch(n){
 case 0:return x.getClass()==X.class&&x.getClass().getName().equals("net.minecraft.test.ClassNameDemo$X")?1:0;
 case 1:return i.getClass()==X.class&&i.getClass().getName()==X.class.getName()?2:0;
 case 2:return String.class.getName()=="java.lang.String"&&String.class.getName()=="java.lang.String".getClass().getName()?3:0;
 case 3:Object a=new String[0];return a.getClass().getName().equals("[Ljava.lang.String;")&&a.getClass().getClassLoader()==null?4:0;
 case 4:Object ints=new int[0];return ints.getClass().getName().equals("[I")&&ints.getClass().getClassLoader()==null?5:0;
 case 5:return x.getClass().getClassLoader()==ClassNameDemo.class.getClassLoader()?6:0;
 case 6:return nil.getClass()==null?0:1;
 case 7:Object obj=new Object();return obj.getClass().getName().equals("java.lang.Object")?7:0;
 case 8:return System.out.getClass().getName().equals("java.io.PrintStream")?8:0;
 default:return 99;
 }}catch(NullPointerException e){return 101;}}
}'''
driver='''import net.minecraft.test.ClassNameDemo;public class ClassNameDriver{public static void main(String[] a){for(String s:a)System.out.println(ClassNameDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-class-name-') as t:
 d=pathlib.Path(t);(d/'ClassNameDemo.java').write_text(source);(d/'ClassNameDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ClassNameDemo.java'),str(d/'ClassNameDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ClassNameDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(9))*10+[-1,9]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ClassNameDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)} operaciones Java de getClass/getName/getClassLoader, interfaz, identidad, arrays y null')
