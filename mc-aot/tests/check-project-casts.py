#!/usr/bin/env python3
"""checkcast/instanceof de clases e interfaces sin defaults en jerarquía acotada."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class CastDemo {
 interface Base {} interface Derived extends Base {} interface Other {}
 static final class A implements Derived {} static final class B implements Base {} static final class C implements Other {}
 static Object a=new A(),b=new B(),c=new C(),str="hi",nil=null,arr=new A[0];
 public static int run(int n){try {switch(n){
 case 0:return (a instanceof A?1:0)+(a instanceof Derived?2:0)+(a instanceof Base?4:0)+(a instanceof Other?8:0);
 case 1:return (b instanceof A?1:0)+(b instanceof Derived?2:0)+(b instanceof Base?4:0)+(b instanceof Object?8:0);
 case 2:return (c instanceof Base?1:0)+(c instanceof Other?2:0)+(str instanceof Base?4:0)+(nil instanceof Base?8:0);
 case 3:return ((Base)a)==a&&((Derived)a)==a&&((A)a)==a?3:0;
 case 4:Derived x=(Derived)b;return -1;
 case 5:A y=(A)c;return -1;
 case 6:Base z=(Base)str;return -1;
 case 7:Base u=(Base)nil;return u==null?7:0;
 case 8:return (arr instanceof A[]?1:0)+(arr instanceof Object[]?2:0)+(arr instanceof String[]?4:0);
 case 9:return (nil instanceof A[]?1:0)+(str instanceof String?2:0)+(nil instanceof Object?4:0);
 case 10:A[] v=(A[])arr;return v.length==0?10:0;
 case 11:A[] w=(A[])(Object)new String[0];return -1;
 default:return 99;
 }}catch(ClassCastException e){return 101;}}
}'''
driver='''import net.minecraft.test.CastDemo;public class CastDriver{public static void main(String[] a){for(String s:a)System.out.println(CastDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-project-cast-') as t:
 d=pathlib.Path(t);(d/'CastDemo.java').write_text(source);(d/'CastDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CastDemo.java'),str(d/'CastDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CastDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(12))*10+[-1,12]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'CastDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)} casts e instanceof Java: interfaz transitiva, clase concreta, arrays, null y ClassCastException')
