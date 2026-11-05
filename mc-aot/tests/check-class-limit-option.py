#!/usr/bin/env python3
"""Límite configurable de clases: 260 clases reales sin confundir cobertura."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-class-limit-') as t:
 d=pathlib.Path(t);src=d/'Many.java';driver=d/'Driver.java'
 src.write_text('package net.minecraft.test; public class Many{public static int run(int n){int x=n;'+''.join(f'x+=C{i}.v();' for i in range(260))+'return x;}}'+''.join(f'class C{i}{{static int v(){{return {i};}}}}' for i in range(260)))
 driver.write_text('import net.minecraft.test.Many;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(Many.run(Integer.parseInt(n)));}}')
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(src),str(driver)],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(limit):
  env=os.environ.copy();env.pop('MC_AOT_MAX_STATIC_CLASSES',None)
  if limit is not None:env['MC_AOT_MAX_STATIC_CLASSES']=limit
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Many',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=240,env=env)
 for limit,want in [(None,'límite experimental de clases estáticas'),('0','debe estar entre 1 y 4096'),('4097','debe estar entre 1 y 4096'),('xx','debe estar entre 1 y 4096')]:
  p=compile(limit)
  if p.returncode==0 or want not in p.stderr:raise AssertionError((limit,p.returncode,p.stderr))
 p=compile('300')
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-20,21));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados con 261 clases y límite opt-in 300; límites inválidos se rechazan')
