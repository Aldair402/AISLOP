#!/usr/bin/env python3
"""Tablas Math.asin/cos usadas por Mth y rechazos de otros operandos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;public class MthMathDemo{public static long asin(int n){return Double.doubleToRawLongBits(Math.asin(n/256.0));}public static long cos(int n){return Double.doubleToRawLongBits(Math.cos(Math.asin(n/256.0)));}public static long bad(){return Double.doubleToRawLongBits(Math.asin(0.1));}}'''
driver='''import net.minecraft.test.MthMathDemo;public class MDriver{public static void main(String[]a){for(int i=0;i<=256;i++){System.out.println(MthMathDemo.asin(i));System.out.println(MthMathDemo.cos(i));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-mth-math-') as t:
 d=pathlib.Path(t);(d/'MthMathDemo.java').write_text(src);(d/'MDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MthMathDemo.java'),str(d/'MDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MthMathDemo',str(d/'native'),'asin','(I)J','cos','(I)J','bad','()J'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'MDriver'],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in range(257) for v in ('0',str(n),'1',str(n))]],capture_output=True,text=True)
 if native.returncode or java!=native.stdout:raise AssertionError((native.returncode,java,native.stdout,native.stderr))
 p=subprocess.run([str(d/'native'),'2'],capture_output=True,text=True)
 if p.returncode==0 or 'fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 514 valores Math.asin/cos de Mth idénticos bit a bit a Java 25; entradas ajenas abortan')
