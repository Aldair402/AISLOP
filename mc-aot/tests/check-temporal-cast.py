#!/usr/bin/env python3
"""Temporal solo para Instant/ZonedDateTime modelados y valores JDK conocidos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.time.*;import java.time.temporal.*;import java.util.*;public class TemporalProbe{public static int run(int n){try{Object x=n%5==0?null:n%5==1?Instant.now():n%5==2?ZonedDateTime.parse("2020-01-02T03:04:05Z"):n%5==3?new Date(0):"x";boolean b=x instanceof Temporal;Temporal t=(Temporal)x;return (b?1:0)+(t==x?2:0);}catch(ClassCastException e){return 9;}}public static int project(int n){Object x=new TemporalProbe();return x instanceof Temporal?1:0;}}'''
driver='''import net.minecraft.test.TemporalProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(TemporalProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-temporal-cast-') as t:
 d=pathlib.Path(t);(d/'TemporalProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'TemporalProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/TemporalProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('project');p=subprocess.run([str(d/'project'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Temporal: objeto proyecto no verificado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Temporal con Instant/ZonedDateTime/null y guardas de clase proyecto')
