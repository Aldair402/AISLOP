#!/usr/bin/env python3
"""new PrintStream está protegido: no se simula apertura de archivos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.io.*;public class PrintStreamGuardProbe{static OutputStream nothing(){return null;}public static int run(int n){if(n==0)return 17;PrintStream p=new PrintStream(nothing());return p==null?1:2;}public static int file(int n)throws Exception{if(n==0)return 17;FileOutputStream f=new FileOutputStream("/not-created");return f==null?1:2;}}'''
driver='''import net.minecraft.test.PrintStreamGuardProbe;public class PrintStreamGuardDriver{public static void main(String[]a){for(String n:a)System.out.println(PrintStreamGuardProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-printstream-guard-') as tmp:
 d=pathlib.Path(tmp);(d/'PrintStreamGuardProbe.java').write_text(source);(d/'PrintStreamGuardDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'PrintStreamGuardProbe.java'),str(d/'PrintStreamGuardDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PrintStreamGuardProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'PrintStreamGuardDriver','0'],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 native=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True,timeout=30)
 if native.returncode==0 or 'new PrintStream: no soportado' not in native.stderr:raise AssertionError(('guard',native.stderr))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PrintStreamGuardProbe',str(d/'native'),'file','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True,timeout=30)
 if native.returncode==0 or 'new FileOutputStream: no soportado' not in native.stderr:raise AssertionError(('file guard',native.stderr))
 print('OK: rama sin PrintStream coincide con Java y construcción PrintStream/FileOutputStream ejecutada aborta explícitamente')
