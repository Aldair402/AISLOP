#!/usr/bin/env python3
"""ThreadLocal exacto sin subclases y con un solo hilo."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class LocalDemo {
 static ThreadLocal<Object> one=new ThreadLocal<>(),two=new ThreadLocal<>(),alias=one,missing;
 static Object a=new Object(),b=new Object();static int val(Object x){return x==null?0:x==a?1:x==b?2:3;}
 public static int set(int w,int v){ThreadLocal<Object> x=w==0?one:two;x.set(v==0?null:v==1?a:b);return val(x.get());}
 public static int get(int w){return val((w==0?alias:two).get());}
 public static void remove(int w){(w==0?one:two).remove();}
 public static int missing(){return val(missing.get());}}
'''
driver='''import net.minecraft.test.LocalDemo;public class LocalDriver{public static void main(String[] a){for(int i=0;i<a.length;){int op=Integer.parseInt(a[i++]);switch(op){case 0->System.out.println(LocalDemo.set(Integer.parseInt(a[i++]),Integer.parseInt(a[i++])));case 1->System.out.println(LocalDemo.get(Integer.parseInt(a[i++])));case 2->{LocalDemo.remove(Integer.parseInt(a[i++]));System.out.println("OK");}}}}}'''
with tempfile.TemporaryDirectory(prefix='mc-threadlocal-') as t:
 d=pathlib.Path(t);(d/'LocalDemo.java').write_text(source);(d/'LocalDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LocalDemo.java'),str(d/'LocalDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LocalDemo',str(d/'native'),'set','(II)I','get','(I)I','remove','(I)V','missing','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(321);args=[]
 for _ in range(150):
  op=rng.randrange(3);args += [str(op),str(rng.randrange(2))]
  if op==0:args.append(str(rng.randrange(3)))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'LocalDriver',*args],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:300],native[:300]))
 p=subprocess.run([str(d/'native'),'3'],capture_output=True,text=True)
 if p.returncode!=2 or 'NullPointerException' not in p.stderr:raise AssertionError(p.stderr)
 print('OK: 150 operaciones ThreadLocal monohilo y null coinciden con Java; subclases e hilos no soportados')
