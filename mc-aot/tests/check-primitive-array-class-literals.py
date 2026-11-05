#!/usr/bin/env python3
"""Identidad y nombre de los ocho literales de arrays primitivos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ArrayClassProbe{public static int run(int n){Class<?> c;Object x;switch(n%8){case 0:c=boolean[].class;x=new boolean[0];break;case 1:c=byte[].class;x=new byte[0];break;case 2:c=char[].class;x=new char[0];break;case 3:c=short[].class;x=new short[0];break;case 4:c=int[].class;x=new int[0];break;case 5:c=long[].class;x=new long[0];break;case 6:c=float[].class;x=new float[0];break;default:c=double[].class;x=new double[0];}return (c==x.getClass()?1:0)+(c.isArray()?2:0)+(c.getName().length()*4);} }'''
driver='''import net.minecraft.test.ArrayClassProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ArrayClassProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-array-class-') as t:
 d=pathlib.Path(t);(d/'ArrayClassProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ArrayClassProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ArrayClassProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados para 8 literales de arrays primitivos')
