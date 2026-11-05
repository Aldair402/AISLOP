#!/usr/bin/env python3
"""URISyntaxException: jerarquía, estado, validación y mensajes UTF-16."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;import java.net.URISyntaxException;public class UriExceptionProbe{public static int run(int n){String input=n%4==0?null:"foo/\ud83d\ude00";String reason=n%5==0?null:"bad";int idx=n%8-3;try{URISyntaxException e=(n&1)==0?new URISyntaxException(input,reason,idx):new URISyntaxException(input,reason);throw e;}catch(URISyntaxException e){String a=e.getMessage(),b=e.getMessage();return a.hashCode()*31+e.getIndex()+(a==b?100:0)+(e.getInput()==input?2:0)+(e.getReason()==reason?4:0)+(e instanceof Exception?8:0);}catch(NullPointerException e){return 11;}catch(IllegalArgumentException e){return 12;}}}'''
driver='''import net.minecraft.test.UriExceptionProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(UriExceptionProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-uri-syntax-') as t:
 d=pathlib.Path(t);(d/'UriExceptionProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UriExceptionProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UriExceptionProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(120));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError([(i,a,b) for i,(a,b) in enumerate(zip(j.splitlines(),n.splitlines())) if a!=b][:12])
 print(f'OK: {len(seq)} resultados URISyntaxException, estado, mensajes y jerarquía frente a Java')
