#!/usr/bin/env python3
"""AtomicReference monohilo: identidad, null, CAS y alias frente a Java."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.concurrent.atomic.AtomicReference;public class AtomicDemo{static Object a=new Object(),b=new Object();static AtomicReference<Object> ref=new AtomicReference<>(a);public static int run(int n){try{switch(n){case 0:return ref.get()==a?1:ref.get()==b?2:3;case 1:return ref.compareAndSet(a,b)?4:5;case 2:return ref.compareAndSet(a,null)?6:7;case 3:return ref.getAndSet(null)==b?8:9;case 4:ref.set(a);return 10;case 5:AtomicReference<Object>x=null;return x.get()==null?1:0;case 6:AtomicReference<Object> x1=new AtomicReference<>();return x1.compareAndSet(null,a)&&x1.get()==a?11:0;default:return 99;}}catch(NullPointerException e){return 105;}}}'''
driver='''import net.minecraft.test.AtomicDemo;public class AtomicDriver{public static void main(String[]a){for(String s:a)System.out.println(AtomicDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-atomic-') as t:
 d=pathlib.Path(t);(d/'AtomicDemo.java').write_text(source);(d/'AtomicDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'AtomicDemo.java'),str(d/'AtomicDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/AtomicDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=[str(n) for n in [0,1,0,2,3,0,4,0,5,6]]*20;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'AtomicDriver',*seq],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} operaciones Java AtomicReference monohilo, compareAndSet, alias y null')
