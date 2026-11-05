#!/usr/bin/env python3
"""Método de referencia Objects::nonNull como Predicate, sin convertir objetos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.*;public class NonNullProbe{public static int run(int n){Predicate<Object> p=Objects::nonNull;Object v=n%3==0?null:n%3==1?"value":new NonNullProbe();return p.test(v)?1:0;}}'''
driver='''import net.minecraft.test.NonNullProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(NonNullProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-objects-nonnull-') as t:
 d=pathlib.Path(t);(d/'NonNullProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'NonNullProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/NonNullProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Objects::nonNull con null, String y objeto traducido')
