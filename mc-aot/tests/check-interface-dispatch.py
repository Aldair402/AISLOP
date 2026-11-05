#!/usr/bin/env python3
"""Despacho cerrado de interfaces sin defaults, múltiples implementadores y valores."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class DispatchDemo {
 interface Op {int apply(int x);String label();void set(int x);}interface Child extends Op {}interface Other {long calc(long x);}
 static final class One implements Op {int n=1;public int apply(int x){return n+x;}public String label(){return "one";}public void set(int x){n=x;}}
 static final class Two implements Child,Other {int n=2;public int apply(int x){return n*x;}public String label(){return "two";}public void set(int x){n=x;}public long calc(long x){return x+7;}}
 static Op a=new One(),b=new Two(),nil=null;static Child child=(Child)b;static Other other=(Other)b;
 public static int run(int n){try{switch(n){case 0:return a.apply(10)+b.apply(10)+child.apply(2);case 1:return a.label().equals("one")&&b.label().equals("two")?1:0;case 2:a.set(5);b.set(7);return a.apply(1)+child.apply(2);case 3:return (int)other.calc(100);case 4:return nil.apply(4);default:return a.apply(n)+b.apply(n);}}catch(NullPointerException e){return 101;}}
}'''
driver='''import net.minecraft.test.DispatchDemo;public class DispatchDriver{public static void main(String[] a){for(String s:a)System.out.println(DispatchDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-iface-dispatch-') as t:
 d=pathlib.Path(t);(d/'DispatchDemo.java').write_text(source);(d/'DispatchDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DispatchDemo.java'),str(d/'DispatchDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DispatchDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(5))*20+[-10,20]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DispatchDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)} operaciones Java de despacho de interfaz, implementadores, herencia de interfaz, alias, int/long/String/void y null')
