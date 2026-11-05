#!/usr/bin/env python3
"""Short.valueOf/shortValue/casts y caché Java -128..127."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.io.*;public class ShortProbe{public static int run(int n){try{Object o=n%7==0?null:n%7==1?"x":Short.valueOf((short)n);if(o==null)return 4;if(!(o instanceof Short)||!(o instanceof Number)||!(o instanceof Serializable)||o.getClass()!=Short.class)return 8;Short s=(Short)o;return s.shortValue()*2+(s==Short.valueOf((short)n)?1:0);}catch(ClassCastException e){return 9;}}}'''
driver='''import net.minecraft.test.ShortProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ShortProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-short-box-') as t:
 d=pathlib.Path(t);(d/'ShortProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ShortProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ShortProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-300,301))+[-32768,32767,65535,65536];j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Short boxing/caché/cast/clase frente a Java')
