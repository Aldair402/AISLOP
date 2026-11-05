#!/usr/bin/env python3
"""HashSet<Class<?>> para deduplicación por clase usada por Log4j."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;
public class ClassSetProbe {
 public static int run(int n){Set<Object> s=new HashSet<>();Object a=new A(),a2=new A(),b=new B();Collection<Object> c=s;int score=0;
  if(c.add(a.getClass()))score+=1;if(s.add(a2.getClass()))score+=2;if(s.add(b.getClass()))score+=4;
  if(s.add(A.class))score+=8;if(s.add(null))score+=16;if(s.add("A"))score+=32;
  if(s.contains(A.class))score+=64;if(s.contains(B.class))score+=128;if(s.contains("A"))score+=256;
  if((n&1)==0 && s.remove(a.getClass()))score+=512;if((n&2)!=0 && s.remove(null))score+=1024;
  if(s.contains(A.class))score+=2048;return score+s.size()*4096;
 }
 public static int bad(){Set<Object> s=new HashSet<>();s.add(new A());return s.size();}
}
final class A {} final class B {}
'''
driver='''import net.minecraft.test.ClassSetProbe;public class ClassSetDriver {public static void main(String[]a){for(String n:a)System.out.println(ClassSetProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-class-set-') as temp:
 d=pathlib.Path(temp);(d/'ClassSetProbe.java').write_text(source);(d/'ClassSetDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ClassSetProbe.java'),str(d/'ClassSetDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ClassSetProbe',str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ClassSetDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or native.stdout!=java.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 bad=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True,timeout=10)
 if bad.returncode==0 or 'HashSet: solo String/Class/null soportado' not in bad.stderr:raise AssertionError(('objeto no soportado',bad.returncode,bad.stderr))
 print(f'OK: {len(vals)} operaciones HashSet con Class/String/null y getClass de objetos, add por Collection, frente a Java; rechazo de claves arbitrarias')
