#!/usr/bin/env python3
"""CharSequence.toString para String/StringBuilder sin despacho arbitrario."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class CharSeqProbe{static final class Other implements CharSequence{public int length(){return 1;}public char charAt(int i){return 'x';}public CharSequence subSequence(int a,int b){return this;}public String toString(){return "x";}}
public static int run(int n){try{CharSequence c=n%4==0?null:n%4==1?"abc":n%4==2?new StringBuilder():new StringBuilder("abc");String a=c.toString(),b=c.toString();return (a==c?1:0)+(a==b?2:0)+(a.equals("abc")?4:0)+(a.equals("")?8:0);}catch(NullPointerException e){return 100;}}
public static int other(int n){CharSequence c=new Other();return c.toString().length();}}'''
driver='''import net.minecraft.test.CharSeqProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(CharSeqProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-charseq-string-') as t:
 d=pathlib.Path(t);(d/'CharSeqProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CharSeqProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CharSeqProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('other');p=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'CharSequence.toString: receptor fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados CharSequence.toString en String/StringBuilder/null; proyecto fuera del perfil aborta')
