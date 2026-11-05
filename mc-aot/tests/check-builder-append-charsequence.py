#!/usr/bin/env python3
"""StringBuilder.append(CharSequence) con String, Builder, self y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class AppendCharSeqProbe{static final class C implements CharSequence{public int length(){return 1;}public char charAt(int i){return 'x';}public CharSequence subSequence(int a,int b){return this;}}public static int run(int n){try{StringBuilder b=(n&8)!=0?null:new StringBuilder("ab");CharSequence c=n%4==0?null:n%4==1?"😀":n%4==2?new StringBuilder("xy"):b;StringBuilder out=b.append(c);return (out==b?1:0)+out.toString().hashCode();}catch(NullPointerException e){return 7;}}public static int other(int n){StringBuilder b=new StringBuilder();CharSequence c=new C();return b.append(c).length();}}'''
driver='''import net.minecraft.test.AppendCharSeqProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(AppendCharSeqProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-append-charsequence-') as t:
 d=pathlib.Path(t);(d/'AppendCharSeqProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'AppendCharSeqProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/AppendCharSeqProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('other');p=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'StringBuilder.append(CharSequence): receptor fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados append(CharSequence) String/Builder/self/null; proyecto fuera del perfil aborta')
