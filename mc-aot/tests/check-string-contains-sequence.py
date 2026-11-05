#!/usr/bin/env python3
"""String.contains para String/StringBuilder sobre unidades UTF-16 y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class ContainsProbe{static final class C implements CharSequence{public int length(){return 0;}public char charAt(int n){return 'x';}public CharSequence subSequence(int a,int b){return this;}}public static int run(int n){String[] hay={"","abcabc","\ud83d\ude00x\ud83d\ude00","\ud83dX\ude00",null};String[] q={"","abc","bc","\ud83d","\ude00","\ud83d\ude00","X","z",null};try{String s=hay[n/18];String x=q[(n/2)%9];CharSequence c=(n%2)==0||x==null?x:new StringBuilder(x);return s.contains(c)?1:0;}catch(NullPointerException e){return 2;}}public static int other(int n){return "abc".contains(new C())?1:0;}}'''
driver='''import net.minecraft.test.ContainsProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ContainsProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-contains-sequence-') as t:
 d=pathlib.Path(t);(d/'ContainsProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ContainsProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 for m in ('run','other'):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ContainsProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(90));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'String.contains: CharSequence fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados String.contains frente a Java y guarda CharSequence de proyecto')
