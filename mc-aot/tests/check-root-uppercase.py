#!/usr/bin/env python3
"""Mayúsculas ASCII con Locale.ROOT y separador del sistema Linux."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.Locale;public class RootUpperDemo{public static int run(int n){switch(n%5){case 0:return "hello-29".toUpperCase(Locale.ROOT).charAt(0);case 1:String s="ABC";return s.toUpperCase(Locale.ROOT)==s?1:0;case 2:return System.lineSeparator()==System.lineSeparator()?2:0;case 3:return System.lineSeparator()=="\\n"?0:3;default:return System.lineSeparator().charAt(0);}}public static int unsupported(){return "é".toUpperCase(Locale.ROOT).length();}}'''
driver='''import net.minecraft.test.RootUpperDemo;public class UpperDriver{public static void main(String[]a){for(String x:a)System.out.println(RootUpperDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-root-upper-') as t:
 d=pathlib.Path(t);(d/'RootUpperDemo.java').write_text(src);(d/'UpperDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RootUpperDemo.java'),str(d/'UpperDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RootUpperDemo',str(d/'native'),'run','(I)I','unsupported','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(50));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'UpperDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'solo ASCII ROOT' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 50 operaciones de mayúsculas ASCII ROOT y lineSeparator; Unicode no soportado aborta')
