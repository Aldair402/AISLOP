#!/usr/bin/env python3
"""cast e instanceof URI final para perfiles CommonLinks."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.net.URI;public class UriCastProbe{public static int run(int n){Object x=n%4==0?null:n%4==1?URI.create("https://aka.ms/MinecraftEULA"):n%4==2?"x":new UriCastProbe();try{boolean y=x instanceof URI;URI u=(URI)x;return(y?1:0)+(u==x?2:0);}catch(ClassCastException e){return 7;}}}'''
driver='''import net.minecraft.test.UriCastProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(UriCastProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-uri-cast-') as t:
 d=pathlib.Path(t);(d/'UriCastProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UriCastProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UriCastProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} casts e instanceof URI/null/String/proyecto')
