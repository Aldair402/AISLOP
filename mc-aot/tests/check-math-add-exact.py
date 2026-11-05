#!/usr/bin/env python3
"""Math.addExact(int,int), bordes y ArithmeticException frente a Java."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ExactProbe{public static int run(int a,int b){try{return Math.addExact(a,b);}catch(ArithmeticException e){return e.getMessage().equals("integer overflow")?42:43;}}}'''
driver='''import net.minecraft.test.ExactProbe;public class Driver{public static void main(String[]a){for(int i=0;i<a.length;i+=2)System.out.println(ExactProbe.run(Integer.parseInt(a[i]),Integer.parseInt(a[i+1])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-add-exact-') as t:
 d=pathlib.Path(t);(d/'ExactProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ExactProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ExactProbe',str(d/'native'),'run','(II)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 edge=[-2147483648,-2147483647,-1,0,1,2147483646,2147483647];rng=random.Random(25);seq=[(a,b) for a in edge for b in edge]+[(rng.randint(-2147483648,2147483647),rng.randint(-2147483648,2147483647)) for _ in range(200)];j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*[str(x) for pair in seq for x in pair]],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for a,b in seq for v in ('0',str(a),str(b))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Math.addExact(int,int), límites y excepciones Java')
