#!/usr/bin/env python3
"""Interfaces sin defaults y despacho directo cerrado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class InterfaceDemo {static int count=1;static C obj=new C(5);static int increment(){return ++count;}public static int result(){return count*100+obj.get();}public static int useInterface(){Iface a=obj;return a.get();}}
interface Parent {int mark=InterfaceDemo.increment();int get();} interface Iface extends Parent {}
class C implements Iface,Runnable {int v;C(int x){v=x;}public int get(){return v;}public void run(){}}
'''
driver='''import net.minecraft.test.InterfaceDemo;public class InterfaceDriver{public static void main(String[] args){System.out.println(InterfaceDemo.result());System.out.println(InterfaceDemo.result());}}'''
with tempfile.TemporaryDirectory(prefix='mc-interfaces-') as t:
 d=pathlib.Path(t);(d/'InterfaceDemo.java').write_text(source);(d/'InterfaceDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InterfaceDemo.java'),str(d/'InterfaceDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/InterfaceDemo']
 p=subprocess.run(base+[str(d/'native'),'result','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'InterfaceDriver'],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if java!=native or native!='105\n105\n':raise AssertionError((java,native))
 p=subprocess.run(base+[str(d/'unsupported'),'useInterface','()I'],capture_output=True,text=True)
 if p.returncode:raise AssertionError(p.stderr)
 native=subprocess.run([str(d/'unsupported'),'0'],capture_output=True,text=True,check=True).stdout
 if native!='5\n':raise AssertionError(native)
 print('OK: implementadores sin defaults no inicializan interfaces y el despacho directo coincide')
