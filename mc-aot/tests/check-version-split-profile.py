#!/usr/bin/env python3
"""String.split específico de Constants.getMajorVersion en Log4j."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class VersionSplitProbe{public static int run(int n){try{String[] cases={"","25.0.5","1.8.0_461","-foo",".x","..","a-b-c-d","😀.a","a.","--.",null};String s=cases[n%11];String[] out=s.split("-|\\.",3);int v=out.length+(out[0]==s?100:0);for(String x:out)v=v*31+x.hashCode();return v;}catch(NullPointerException e){return 77;}}public static int bad(int n){return "1.8".split("x",3).length;}public static int limit(int n){return "1.8".split("-|\\.",2).length;}}'''
driver='''import net.minecraft.test.VersionSplitProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(VersionSplitProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-version-split-') as t:
 d=pathlib.Path(t);(d/'VersionSplitProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'VersionSplitProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/VersionSplitProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(110));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 for method in ['bad','limit']:
  compile(method);p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or 'String.split: solo patrón y límite de versión Log4j' not in p.stderr:raise AssertionError((method,p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados split versión Log4j, identidad, límites, vacíos y UTF-16; otros patrones/límites abortan')
