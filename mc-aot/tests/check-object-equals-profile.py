#!/usr/bin/env python3
"""Object.equals despachado a Class/String, rechaza receptores desconocidos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class EqualityProbe{static final class Other{}public static int run(int n){try{Object a=n%4==0?null:n%4==1?EqualityProbe.class:n%4==2?"hola":"other";Object b=(n&1)==0?"hola":EqualityProbe.class;return a.equals(b)?1:0;}catch(NullPointerException e){return 2;}}public static int unsupported(int n){Object x=new Other();return x.equals(x)?1:0;}}'''
driver='''import net.minecraft.test.EqualityProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(EqualityProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-object-equals-') as t:
 d=pathlib.Path(t);(d/'EqualityProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EqualityProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EqualityProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('unsupported');p=subprocess.run([str(d/'unsupported'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Object.equals: receptor fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Object.equals en Class/String/null; otro receptor aborta')
