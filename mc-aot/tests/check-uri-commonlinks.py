#!/usr/bin/env python3
"""URI.create solo admite literales CommonLinks, con identidad de toString."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.net.URI;public class UDemo{public static int run(int n){String s=n%2==0?"https://aka.ms/MinecraftEULA":"https://aka.ms/MinecraftGDPR";URI u=URI.create(s);return (u.toString()==s?100:0)+(String.valueOf((Object)u)==s?10:0)+u.toString().length();}public static int bad(){return URI.create("https://example.com/").toString().length();}}'''
driver='''import net.minecraft.test.UDemo;public class UDriver{public static void main(String[]a){for(String x:a)System.out.println(UDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-uri-') as t:
 d=pathlib.Path(t);(d/'UDemo.java').write_text(src);(d/'UDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UDemo.java'),str(d/'UDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UDemo',str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(60));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'UDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'fuera del perfil CommonLinks' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 60 URI CommonLinks e identidad contra Java; URI fuera del perfil aborta')
