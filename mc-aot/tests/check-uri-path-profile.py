#!/usr/bin/env python3
"""URI.getPath en literales CommonLinks con query y sin query."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.net.URI;public class UriPathProbe{public static int run(int n){try{URI u=n%4==0?null:URI.create(n%4==1?"https://aka.ms/MinecraftEULA":n%4==2?"http://go.microsoft.com/fwlink/?LinkId=521839":"https://aka.ms/snapshotfeedback?ref=game");String s=u.getPath();return s.hashCode()+(s==u.getPath()?1:0);}catch(NullPointerException e){return -1;}}}'''
driver='''import net.minecraft.test.UriPathProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(UriPathProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-uri-path-') as t:
 d=pathlib.Path(t);(d/'UriPathProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UriPathProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UriPathProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados URI.getPath CommonLinks, identidad y null')
