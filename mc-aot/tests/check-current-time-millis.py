#!/usr/bin/env python3
"""System.currentTimeMillis contra reloj de pared Java y límites del host."""
import os,pathlib,subprocess,tempfile,time
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ClockProbe{public static long run(int n){return System.currentTimeMillis();}}'''
driver='''import net.minecraft.test.ClockProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ClockProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-clock-') as t:
 d=pathlib.Path(t);(d/'ClockProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ClockProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ClockProbe',str(d/'native'),'run','(I)J'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(81));before=time.time_ns()//1000000
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True,timeout=30);after=time.time_ns()//1000000
 for label,p in [('Java',java),('nativo',native)]:
  vals=[int(x) for x in p.stdout.splitlines()]
  if len(vals)!=len(seq) or any(x<before-250 or x>after+250 for x in vals):raise AssertionError((label,before,after,vals))
 print(f'OK: {len(seq)*2} lecturas Java/nativas en la ventana del reloj del host; no se supone monotonía')
