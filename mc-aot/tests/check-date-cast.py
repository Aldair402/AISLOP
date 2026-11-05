#!/usr/bin/env python3
"""Date cast de objeto exacto; subclases de proyecto se rechazan."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class DateCastProbe{public static int run(int n){try{Object x=n%3==0?null:n%3==1?new Date(0):"x";boolean b=x instanceof Date;Date d=(Date)x;return (b?1:0)+(d==x?2:0);}catch(ClassCastException e){return 9;}}public static int project(int n){Object x=new DateCastProbe();return x instanceof Date?1:0;}}'''
driver='''import net.minecraft.test.DateCastProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(DateCastProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-date-cast-') as t:
 d=pathlib.Path(t);(d/'DateCastProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DateCastProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DateCastProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('project');p=subprocess.run([str(d/'project'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Date: objeto proyecto no verificado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Date/null/cast; clases proyecto no verificadas abortan')
