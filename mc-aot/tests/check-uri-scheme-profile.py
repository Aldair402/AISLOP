#!/usr/bin/env python3
"""URI.getScheme para los literales CommonLinks y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.net.URI;public class UriSchemeProbe{public static int run(int n){try{URI u=n%3==0?null:URI.create(n%3==1?"https://aka.ms/MinecraftEULA":"http://go.microsoft.com/fwlink/?LinkId=521839");String s=u.getScheme();return s.hashCode()+(s==u.getScheme()?1:0);}catch(NullPointerException e){return -1;}}}'''
driver='''import net.minecraft.test.UriSchemeProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(UriSchemeProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-uri-scheme-') as t:
 d=pathlib.Path(t);(d/'UriSchemeProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UriSchemeProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UriSchemeProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados URI.getScheme CommonLinks, identidad y null')
