#!/usr/bin/env python3
"""Registro de clase Comparator propia; dispatch por Comparator sigue restringido."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class ComparatorClassProbe{static final class C implements Comparator<String>{public int compare(String a,String b){return a.length()-b.length();}}public static int run(int n){Object c=new C();return (c instanceof C?2:0)+(c.getClass()==C.class?4:0);}public static int compare(int n){Comparator<String> c=new C();return c.compare("A","BB");}}'''
driver='''import net.minecraft.test.ComparatorClassProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ComparatorClassProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-comparator-class-') as t:
 d=pathlib.Path(t);(d/'ComparatorClassProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ComparatorClassProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ComparatorClassProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('compare');p=subprocess.run([str(d/'compare'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Comparator.compare: comparador fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados de registro/clase Comparator y guarda de compare')
