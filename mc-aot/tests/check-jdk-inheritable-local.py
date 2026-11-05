#!/usr/bin/env python3
"""Subclases directas InheritableThreadLocal con semántica monohilo y guardas de overrides."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class InheritableDemo {
 static InheritableThreadLocal<Object> first=new Child(1),second=new Child(2),alias=first;static Object a=new Object(),b=new Object();
 static int val(Object v){return v==null?0:v==a?1:v==b?2:3;}
 public static int set(int w,int v){InheritableThreadLocal<Object> t=w==0?first:second;t.set(v==0?null:v==1?a:b);return val(t.get());}
 public static int get(int w){return val((w==0?alias:second).get());}
 public static void reset(int w){(w==0?first:second).remove();}
}
class Child extends InheritableThreadLocal<Object>{int marker;Child(int x){marker=x;}protected Object childValue(Object v){return v;}}
class BadInitial extends InheritableThreadLocal<Object>{protected Object initialValue(){return new Object();}}
class BadGet extends InheritableThreadLocal<Object>{public Object get(){return new Object();}}
class BadSet extends InheritableThreadLocal<Object>{public void set(Object o){}}
class BadRemove extends InheritableThreadLocal<Object>{public void remove(){}}
class InitialGuard {static int run(){new BadInitial();return 1;}}class GetGuard {static int run(){new BadGet();return 1;}}class SetGuard {static int run(){new BadSet();return 1;}}class RemoveGuard {static int run(){new BadRemove();return 1;}}
'''
driver='''import net.minecraft.test.InheritableDemo;public class InheritableDriver{public static void main(String[] a){for(int i=0;i<a.length;){int op=Integer.parseInt(a[i++]);switch(op){case 0->System.out.println(InheritableDemo.set(Integer.parseInt(a[i++]),Integer.parseInt(a[i++])));case 1->System.out.println(InheritableDemo.get(Integer.parseInt(a[i++])));case 2->{InheritableDemo.reset(Integer.parseInt(a[i++]));System.out.println("OK");}}}}}'''
with tempfile.TemporaryDirectory(prefix='mc-inheritable-local-') as t:
 d=pathlib.Path(t);(d/'InheritableDemo.java').write_text(source);(d/'InheritableDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InheritableDemo.java'),str(d/'InheritableDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/InheritableDemo',str(d/'native'),'set','(II)I','get','(I)I','reset','(I)V'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(375);args=[]
 for _ in range(150):
  op=rng.randrange(3);args += [str(op),str(rng.randrange(2))]
  if op==0:args.append(str(rng.randrange(3)))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'InheritableDriver',*args],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:300],native[:300]))
 for name in ['InitialGuard','GetGuard','SetGuard','RemoveGuard']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/'+name,str(d/name),'run','()I'],capture_output=True,text=True)
  if p.returncode==0 or 'override ThreadLocal no soportado' not in p.stderr:raise AssertionError((name,p.stderr))
 print('OK: 150 operaciones de subclase InheritableThreadLocal monohilo; 4 overrides incompatibles rechazados')
