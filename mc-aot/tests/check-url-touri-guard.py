#!/usr/bin/env python3
"""URL.toURI: null tiene NPE; URL real todavía se rechaza."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.net.*;public class UrlUriProbe{public static int run(int n){try{URL u=null;return u.toURI()==null?1:0;}catch(NullPointerException e){return 2;}catch(URISyntaxException e){return 3;}}public static int other(int n){try{return new URL("https://example.com").toURI()==null?1:0;}catch(Exception e){return 3;}}}'''
driver='''import net.minecraft.test.UrlUriProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(UrlUriProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-url-uri-') as t:
 d=pathlib.Path(t);(d/'UrlUriProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UrlUriProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(m):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UrlUriProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(50));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=compile('other')
 if p.returncode==0 or 'new no soportado: java/net/URL' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} casos URL.toURI null frente a Java; URL real rechazada')
