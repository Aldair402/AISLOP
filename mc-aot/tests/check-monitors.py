#!/usr/bin/env python3
"""Class literals sin inicialización y bloques monitor anidados, solo monohilo."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class MonitorDemo {
 static Object lock=new Object();static int counter=1;static int bump(){return ++counter;}
 static Class<?> type(){return Lazy.class;}
 public static int literal(){return (type()==Lazy.class?100:0)+counter;}
 public static int run(int n){synchronized(lock){counter+=n;synchronized(lock){counter+=2;}synchronized(MonitorDemo.class){counter+=3;}return counter;}}
 public static int finallyExit(int n){try {synchronized(lock){if(n==0)throw new IllegalArgumentException();counter+=n;}}catch(IllegalArgumentException e){return counter;}return counter;}
 public static int nothing(){Object o=null;synchronized(o){return 0;}}
}
class Lazy {static int n=MonitorDemo.bump();}
'''
driver='''import net.minecraft.test.MonitorDemo;public class MonitorDriver{public static void main(String[] a){System.out.println(MonitorDemo.literal());for(String s:a){int n=Integer.parseInt(s);System.out.println(MonitorDemo.run(n));System.out.println(MonitorDemo.finallyExit(n));}System.out.println(MonitorDemo.literal());}}'''
with tempfile.TemporaryDirectory(prefix='mc-monitors-') as t:
 d=pathlib.Path(t);(d/'MonitorDemo.java').write_text(source);(d/'MonitorDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MonitorDemo.java'),str(d/'MonitorDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MonitorDemo',str(d/'native'),'literal','()I','run','(I)I','finallyExit','(I)I','nothing','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(424);vals=[-2147483648,-1,0,1,2147483647]+[rng.randint(-5000,5000) for _ in range(60)]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'MonitorDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
 args=['0'];
 for n in vals:args+=['1',str(n),'2',str(n)]
 args+=['0'];native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:300],native[:300]))
 if java.splitlines()[0]!='101':raise AssertionError(java[:20])
 p=subprocess.run([str(d/'native'),'3'],capture_output=True,text=True)
 if p.returncode!=2 or 'NullPointerException' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {2+len(vals)*2} operaciones con Class literal, monitores reentrantes y finally; null coincide por categoría; solo un hilo')
