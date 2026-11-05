#!/usr/bin/env python3
"""subSequence sobre String/StringBuilder, índices UTF-16 y efectos de identidad."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class CharSubProbe{static final class C implements CharSequence{public int length(){return 1;}public char charAt(int i){return 'x';}public CharSequence subSequence(int a,int b){return this;}}public static int run(int n){try{CharSequence c=n/36==0?"a😀b":n/36==1?new StringBuilder("a😀b"):null;int begin=(n%36)/6-1,end=n%6-1;CharSequence a=c.subSequence(begin,end),b=c.subSequence(begin,end);return (a==c?1:0)+(a==b?2:0)+((String)a).hashCode()*3;}catch(NullPointerException e){return 10;}catch(IndexOutOfBoundsException e){return 20;}}public static int other(int n){CharSequence c=new C();return c.subSequence(0,1).length();}}'''
driver='''import net.minecraft.test.CharSubProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(CharSubProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-charsequence-sub-') as t:
 d=pathlib.Path(t);(d/'CharSubProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CharSubProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CharSubProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(108));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('other');p=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'CharSequence.subSequence: receptor fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados CharSequence.subSequence UTF-16, identidad e índices; proyectos no admitidos abortan')
