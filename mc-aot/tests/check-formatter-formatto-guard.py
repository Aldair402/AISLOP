#!/usr/bin/env python3
"""No se simula DateTimeFormatter.formatTo con zona o locale incorrectas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.time.*;import java.time.format.*;public class FormatToGuard{public static int run(int n){if(n==0)return 7;StringBuilder b=new StringBuilder();DateTimeFormatter.ISO_INSTANT.formatTo(Instant.now(),b);return b.length();}}'''
driver='''import net.minecraft.test.FormatToGuard;public class Driver{public static void main(String[]a){System.out.println(FormatToGuard.run(0));}}'''
with tempfile.TemporaryDirectory(prefix='mc-formatto-guard-') as t:
 d=pathlib.Path(t);(d/'FormatToGuard.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FormatToGuard.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FormatToGuard',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True)
 if p.returncode==0 or 'DateTimeFormatter.formatTo: formateo de fecha no implementado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: rama sin formatTo coincide con Java; formateo de fecha aborta explícitamente')
