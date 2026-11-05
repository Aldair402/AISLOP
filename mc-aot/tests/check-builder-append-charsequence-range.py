#!/usr/bin/env python3
"""append(CharSequence,int,int): UTF-16, rangos, identidad, capacidad y alias."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class RangeProbe{
 static class C implements CharSequence{public int length(){return 1;}public char charAt(int i){return 'x';}public CharSequence subSequence(int a,int b){return this;}}
 public static int run(int n){int mode=n%5,lo=(n/5)%9-2,hi=(n/45)%9-2,cap=(n/405)%6;StringBuilder b=new StringBuilder(cap);b.append("ab");CharSequence x=mode==0?null:mode==1?"a\u0100b":mode==2?new StringBuilder("a\u0100b"):mode==3?b:"\ud83d\ude00z";try{StringBuilder out=b.append(x,lo,hi);return out.toString().hashCode()*31+out.capacity()+(out==b?1:0);}catch(IndexOutOfBoundsException e){return e.getMessage().hashCode();}}
 public static int other(int n){return new StringBuilder().append(new C(),0,1).length();}
}'''
driver='''import net.minecraft.test.RangeProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(RangeProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-append-range-') as t:
 d=pathlib.Path(t);(d/'RangeProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RangeProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(m):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RangeProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((m,p.stderr))
 compile('run');compile('other');seq=list(range(2430));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:
  a=j.splitlines();b=n.splitlines();raise AssertionError([(i,a[i],b[i]) for i in range(len(a)) if a[i]!=b[i]][:12])
 p=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'fuente fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Java 25 y guarda CharSequence de proyecto')
