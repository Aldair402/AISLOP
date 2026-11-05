#!/usr/bin/env python3
"""Objects.toString(Object,String) solo String/StringBuilder/null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class ObjectsStringProbe{public static int run(int n){Object obj=n%4==0?null:n%4==1?"ABC":n%4==2?new StringBuilder("ABC"):new StringBuilder();String fallback=(n&8)==0?null:"fallback";String x=Objects.toString(obj,fallback);return x==null?100:(x==obj?1:0)+(x==fallback?2:0)+x.length()*10;}public static int other(int n){return Objects.toString(new ObjectsStringProbe(),null).length();}}'''
driver='''import net.minecraft.test.ObjectsStringProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ObjectsStringProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-objects-string-') as t:
 d=pathlib.Path(t);(d/'ObjectsStringProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ObjectsStringProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ObjectsStringProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('other');p=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Objects.toString: receptor fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Objects.toString con null/String/StringBuilder, identidad y guarda de objetos')
