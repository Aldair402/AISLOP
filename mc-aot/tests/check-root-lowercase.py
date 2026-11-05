#!/usr/bin/env python3
"""toLowerCase(Locale.ROOT) ASCII sin depender del idioma predeterminado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class RootLowerProbe{public static int run(int n){try{String s=n%4==0?null:n%4==1?"ALIAS-I":n%4==2?"unchanged-123":"";Locale l=(n&8)!=0?null:Locale.ROOT;String x=s.toLowerCase(l);return (x==s?1:0)+x.hashCode();}catch(NullPointerException e){return 7;}}public static int unicode(int n){return "é".toLowerCase(Locale.ROOT).length();}}'''
driver='''import net.minecraft.test.RootLowerProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(RootLowerProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-root-lower-') as t:
 d=pathlib.Path(t);(d/'RootLowerProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RootLowerProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RootLowerProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-Duser.language=tr','-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;env=os.environ.copy();env.pop('MC_AOT_JAVA_LANGUAGE',None);n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True,env=env).stdout
 if j!=n:raise AssertionError((j,n))
 compile('unicode');p=subprocess.run([str(d/'unicode'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'solo ASCII ROOT' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Java Locale.ROOT, identidad y null con idioma tr; Unicode aborta')
