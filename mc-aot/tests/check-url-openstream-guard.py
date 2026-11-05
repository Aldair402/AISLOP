#!/usr/bin/env python3
"""URL.openStream solo ofrece el error explícito para URL no soportada."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.net.*;import java.io.*;public class UrlGuardProbe{
 public static int run(int n){try{URL u=null;return u.openStream()==null?1:0;}catch(NullPointerException e){return 2;}catch(IOException e){return 3;}}
 public static int create(int n){try{return new URL("https://example.com").openStream()==null?1:0;}catch(IOException e){return 3;}}
}'''
driver='''import net.minecraft.test.UrlGuardProbe;public class UrlGuardDriver{public static void main(String[]a){for(String n:a)System.out.println(UrlGuardProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-url-guard-') as tmp:
 d=pathlib.Path(tmp);(d/'UrlGuardProbe.java').write_text(source);(d/'UrlGuardDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UrlGuardProbe.java'),str(d/'UrlGuardDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UrlGuardProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(30));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'UrlGuardDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('create')
 if p.returncode==0 or 'new no soportado: java/net/URL' not in p.stderr:raise AssertionError(('URL guard',p.stderr))
 print(f'OK: {len(vals)} casos URL.openStream con receptor null frente a Java; creación y apertura real de URL no soportadas')
