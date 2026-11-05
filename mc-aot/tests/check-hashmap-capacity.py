#!/usr/bin/env python3
"""HashMap(int) limitado: excepciones y operaciones sin depender del orden."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class HashMapCapacityProbe{public static int run(int n){try{HashMap<String,String> m=new HashMap<>(n);m.put("a","b");m.put(null,"x");return m.size()+(m.get("a")=="b"?4:0)+(m.containsKey(null)?8:0);}catch(IllegalArgumentException e){return e.getMessage().hashCode();}}}'''
driver='''import net.minecraft.test.HashMapCapacityProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(HashMapCapacityProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-hashmap-cap-') as t:
 d=pathlib.Path(t);(d/'HashMapCapacityProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'HashMapCapacityProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/HashMapCapacityProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','1000001'],capture_output=True,text=True)
 if p.returncode==0 or 'HashMap: capacidad experimental excedida' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados HashMap(int), operaciones y guarda de capacidad')
