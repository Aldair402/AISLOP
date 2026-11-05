#!/usr/bin/env python3
"""Date.toInstant/toEpochMilli, extremos signed y negativos con redondeo."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class DateInstantProbe{public static long run(long n){return new Date(n).toInstant().toEpochMilli();}public static int nul(int n){try{Date d=null;return d.toInstant()==null?0:1;}catch(NullPointerException e){return 7;}}}'''
driver='''import net.minecraft.test.DateInstantProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(DateInstantProbe.run(Long.parseLong(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-date-instant-') as t:
 d=pathlib.Path(t);(d/'DateInstantProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DateInstantProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method,desc):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DateInstantProbe',str(d/method),method,desc],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run','(J)J');rng=random.Random(25);seq=[-2**63,-2**63+1,-1001,-1000,-999,-1,0,1,999,1000,1001,2**63-2,2**63-1]+[rng.randrange(-2**63,2**63) for _ in range(200)];j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('nul','(I)I');p=subprocess.run([str(d/'nul'),'0','0'],capture_output=True,text=True,check=True)
 if p.stdout!='7\n':raise AssertionError(p.stdout)
 print(f'OK: {len(seq)+1} casos Date.toInstant/toEpochMilli, extremos i64, negativos y null')
