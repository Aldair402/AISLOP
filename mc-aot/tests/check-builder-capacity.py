#!/usr/bin/env python3
"""StringBuilder(int): capacidades acotadas y NegativeArraySizeException."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class BuilderCapacityProbe{public static int run(int n){try{StringBuilder b=new StringBuilder(n);return b.append("hello").toString().length();}catch(NegativeArraySizeException e){return e.getMessage().hashCode();}}public static int huge(int n){return new StringBuilder(1000001).length();}}'''
driver='''import net.minecraft.test.BuilderCapacityProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(BuilderCapacityProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-builder-cap-') as t:
 d=pathlib.Path(t);(d/'BuilderCapacityProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'BuilderCapacityProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/BuilderCapacityProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41))+[1000,1000000,-2147483648];j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('huge');p=subprocess.run([str(d/'huge'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'capacidad fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados StringBuilder(int), capacidad acotada y excepción negativa')
