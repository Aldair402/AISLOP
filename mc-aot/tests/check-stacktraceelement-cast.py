#!/usr/bin/env python3
"""Solo null y valores no StackTraceElement: no se crean frames ficticios."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ElementCastProbe{public static int run(int n){try{Object x=n%3==0?null:n%3==1?"x":new ElementCastProbe();boolean b=x instanceof StackTraceElement;StackTraceElement y=(StackTraceElement)x;return (b?1:0)+(y==x?2:0);}catch(ClassCastException e){return 9;}}}'''
driver='''import net.minecraft.test.ElementCastProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ElementCastProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-stack-element-cast-') as t:
 d=pathlib.Path(t);(d/'ElementCastProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ElementCastProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ElementCastProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} casos null/no StackTraceElement; no se producen elementos reales de stack')
