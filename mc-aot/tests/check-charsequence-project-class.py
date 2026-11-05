#!/usr/bin/env python3
"""Inicialización de clase que implementa CharSequence de Java 25 sin clinit."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class CharSequenceProbe{static int init;static final class Impl implements CharSequence{static{init++;}public int length(){return 3;}public char charAt(int n){return 'x';}public CharSequence subSequence(int x,int y){return null;}}public static int run(int n){Impl x=new Impl();return init*10+x.length();}public static int unsupported(int n){CharSequence x=new Impl();return x.length();}}'''
driver='''import net.minecraft.test.CharSequenceProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(CharSequenceProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-charsequence-') as t:
 d=pathlib.Path(t);jp=subprocess.run([str(jdk/'javap'),'-p','java.lang.CharSequence'],capture_output=True,text=True,check=True).stdout
 if 'static {};' in jp:raise AssertionError('CharSequence JDK tiene inicializador estático')
 (d/'CharSequenceProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CharSequenceProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CharSequenceProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('unsupported');p=subprocess.run([str(d/'unsupported'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'CharSequence concreto no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados de inicialización para clase CharSequence; llamada a implementación de proyecto por interfaz aborta')
