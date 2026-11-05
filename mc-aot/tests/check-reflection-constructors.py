#!/usr/bin/env python3
"""Reflexión con constructores públicos ()V registrados y estado de clase real."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'ReflectDemo.java':'''package net.minecraft.test;
import java.lang.reflect.*;
public class ReflectDemo {
 public static int count=1;public static IllegalArgumentException marker=new IllegalArgumentException();static Constructor<?> ctor;
 public static int run(int n){try{switch(n){
 case 0:Class<?> c=ReflectDemo.class.getClassLoader().loadClass("net.minecraft.test.Good");return (c==Good.class?1:0)+count*100;
 case 1:ctor=Good.class.getConstructor((Class<?>[])null);return (ctor!=Good.class.getConstructor()?2:0)+count*100;
 case 2:Object o=ctor.newInstance((Object[])null);return (o!=null?3:0)+count*100;
 case 3:ctor.newInstance(new Object[0]);return count;
 case 4:NoDefault.class.getConstructor();return -1;
 case 5:ctor.newInstance("x");return -1;
 case 6:Thrower.class.getConstructor().newInstance();return -1;
 case 7:Failed.class.getConstructor().newInstance();return -1;
 case 8:Failed.class.getConstructor().newInstance();return -1;
 case 9:String.class.getConstructor();return -1;
 case 10:Good.class.getConstructor(String.class);return -1;
 default:return count;
 }}catch(InvocationTargetException e){return e.getCause()==marker && e.getTargetException()==marker?106:-106;}
 catch(NoSuchMethodException e){return 104;}catch(IllegalArgumentException e){return 105;}
 catch(ExceptionInInitializerError e){return 107;}catch(NoClassDefFoundError e){return 108;}
 catch(ReflectiveOperationException e){return -110;}}
}''',
'Good.java':'''package net.minecraft.test;public class Good{static {ReflectDemo.count+=10;}public Good(){ReflectDemo.count++;}}''',
'NoDefault.java':'''package net.minecraft.test;public class NoDefault{public NoDefault(int x){}}''',
'Thrower.java':'''package net.minecraft.test;public class Thrower{public Thrower(){throw ReflectDemo.marker;}}''',
'Failed.java':'''package net.minecraft.test;public class Failed{static int n=1/zero();static int zero(){return 0;}public Failed(){}}''',
'ReflectDriver.java':'''import net.minecraft.test.ReflectDemo;public class ReflectDriver{public static void main(String[] a){for(String s:a)System.out.println(ReflectDemo.run(Integer.parseInt(s)));}}'''}
with tempfile.TemporaryDirectory(prefix='mc-reflect-') as t:
 d=pathlib.Path(t)
 for name,text in sources.items():(d/name).write_text(text)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/x) for x in sources]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 env=dict(os.environ,MC_AOT_REFLECT_CLASSES=':'.join('net/minecraft/test/'+x for x in ('Good','NoDefault','Thrower','Failed')))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ReflectDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['0','1','2','3','4','5','6','7','8','0','3','4','5','6','-1'];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ReflectDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 for n,expected in [('9','clase no registrada'),('10','parámetros no vacíos')]:
  p=subprocess.run([str(d/'native'),'0',n],capture_output=True,text=True)
  if p.returncode!=2 or expected not in p.stderr:raise AssertionError((n,p.returncode,p.stderr))
 print(f'OK: {len(vals)} operaciones Java de reflexión registrada: carga, inicialización, constructores, causa/identidad, fallos y dos guardas explícitas')
