#!/usr/bin/env python3
"""WeakHashMap no se sustituye por un mapa de claves fuertes."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class WeakMapGuard{public static int run(int n){if(n==0)return 17;WeakHashMap<Object,Object> m=new WeakHashMap<>();return m.size();}}'''
driver='''import net.minecraft.test.WeakMapGuard;public class Driver{public static void main(String[]a){System.out.println(WeakMapGuard.run(0));}}'''
with tempfile.TemporaryDirectory(prefix='mc-weakmap-guard-') as t:
 d=pathlib.Path(t);(d/'WeakMapGuard.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'WeakMapGuard.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 # Avoid invoking WeakHashMap methods: compilation guards rather than faking weak semantics.
 source2=source.replace('return m.size();','return m==null?0:1;');(d/'WeakMapGuard.java').write_text(source2);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'WeakMapGuard.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/WeakMapGuard',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True)
 if p.returncode==0 or 'new WeakHashMap: semántica de claves débiles no implementada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: rama sin WeakHashMap coincide con Java; construcción aborta en vez de simular claves fuertes')
