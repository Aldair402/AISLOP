#!/usr/bin/env python3
"""Casts CharSequence para String, StringBuilder y clases de proyecto registradas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class CharCastProbe{static final class C implements CharSequence{public int length(){return 1;}public char charAt(int i){return 'x';}public CharSequence subSequence(int a,int b){return this;}}static final class D{}public static int run(int n){try{Object x=n%5==0?null:n%5==1?"x":n%5==2?new StringBuilder("x"):n%5==3?new C():new D();boolean b=x instanceof CharSequence;CharSequence c=(CharSequence)x;return (b?1:0)+(c==x?2:0);}catch(ClassCastException e){return 9;}}}'''
driver='''import net.minecraft.test.CharCastProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(CharCastProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-charsequence-cast-') as t:
 d=pathlib.Path(t);(d/'CharCastProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CharCastProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CharCastProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados instanceof/cast CharSequence, incluidos null y clase propia')
