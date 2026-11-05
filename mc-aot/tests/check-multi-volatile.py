#!/usr/bin/env python3
"""Lecturas/escrituras volatile solo en ejecución de un hilo, sin afirmar memoria concurrente."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class VolatileDemo {static volatile int n;static volatile long l;static volatile Cell c;static volatile Object alias;
 public static int set(int x){n=x;l=x;c=new Cell();alias=c;c.v=x;c.big=x;return get();}
 public static int get(){return n+(int)l+c.v+(int)c.big+(c==alias?1:0);}
 public static void clear(){c=null;alias=null;}
 public static int empty(){return c==null&&alias==null?1:0;}}
class Cell {volatile int v;volatile long big;}
'''
driver='''import net.minecraft.test.VolatileDemo;public class VolatileDriver{public static void main(String[] a){for(String s:a){System.out.println(VolatileDemo.set(Integer.parseInt(s)));System.out.println(VolatileDemo.get());}VolatileDemo.clear();System.out.println("OK");System.out.println(VolatileDemo.empty());}}'''
with tempfile.TemporaryDirectory(prefix='mc-volatile-') as t:
 d=pathlib.Path(t);(d/'VolatileDemo.java').write_text(source);(d/'VolatileDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'VolatileDemo.java'),str(d/'VolatileDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/VolatileDemo',str(d/'native'),'set','(I)I','get','()I','clear','()V','empty','()I'];p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(777);values=[-2147483648,-1,0,1,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(75)]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'VolatileDriver',*map(str,values)],capture_output=True,text=True,check=True).stdout
 args=sum((['0',str(n),'1'] for n in values),[])+['2','3'];native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:500],native[:500]))
 print(f'OK: {len(values)*2+2} operaciones volatile monohilo coinciden con Java; no hay garantías de concurrencia')
