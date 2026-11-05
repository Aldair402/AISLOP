#!/usr/bin/env python3
"""Collectors.joining: creación diferida; no implementa aún su consumo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.stream.*;
public class JoiningProbe {public static int run(int n){String delimiter=(n&1)!=0?null:",";String prefix=(n&2)!=0?null:"[";String suffix=(n&4)!=0?null:"]";Collector<?,?,?> a=Collectors.joining(delimiter,prefix,suffix);Collector<?,?,?> b=Collectors.joining(delimiter,prefix,suffix);return (a!=null?1:0)+(a!=b?2:0);}
 public static int unsupported(int n){return Collectors.joining(new StringBuilder(","),"[","]")==null?0:1;}}
'''
driver='''import net.minecraft.test.JoiningProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(JoiningProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-joining-') as t:
 d=pathlib.Path(t);(d/'JoiningProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'JoiningProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/JoiningProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('unsupported');p=subprocess.run([str(d/'unsupported'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Collectors.joining: solo String/null soportados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados creación de Collectors.joining, identidad y argumentos null diferidos; CharSequence mutable aborta; sin consumo')
