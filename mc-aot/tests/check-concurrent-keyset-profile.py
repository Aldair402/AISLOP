#!/usr/bin/env python3
"""KeySetView monohilo con String/Class; no prueba concurrencia ni iteración."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.concurrent.*;public class KeySetProbe{
 public static int run(int n){Set<Object> s=ConcurrentHashMap.newKeySet();int r=0;Object[] v={"a","b",String.class,Object.class,"a"};for(int i=0;i<5;i++){if(s.add(v[i]))r+=1;if(s.contains(v[i]))r+=2;}r+=s.size()*10;if((n&1)!=0&&s.remove("a"))r+=100;if((n&2)!=0){try{s.add(null);return -1;}catch(NullPointerException e){r+=200;}}if((n&4)!=0){try{s.contains(null);return -2;}catch(NullPointerException e){r+=400;}}if((n&8)!=0){try{s.remove(null);return -3;}catch(NullPointerException e){r+=800;}}if((n&16)!=0){s.clear();if(s.isEmpty())r+=1600;}return r;}
 public static int bad(int n){Set<Object>s=ConcurrentHashMap.newKeySet();s.add(new Object());return 1;}
 public static int iter(int n){Set<Object>s=ConcurrentHashMap.newKeySet();return s.iterator().hasNext()?1:0;}
}'''
driver='''import net.minecraft.test.KeySetProbe;public class KeySetDriver{public static void main(String[]a){for(String n:a)System.out.println(KeySetProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-keyset-') as tmp:
 d=pathlib.Path(tmp);(d/'KeySetProbe.java').write_text(source);(d/'KeySetDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'KeySetProbe.java'),str(d/'KeySetDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/KeySetProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(96));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'KeySetDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 for method,want in [('bad','solo claves String/Class soportadas'),('iter','iterator de colección no soportada')]:
  p=compile(method)
  if p.returncode:raise RuntimeError(p.stderr)
  n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
  if n.returncode==0 or want not in n.stderr:raise AssertionError((method,n.stderr))
 print(f'OK: {len(vals)} resultados newKeySet monohilo String/Class y null frente a Java; rechaza objetos e iteración')
