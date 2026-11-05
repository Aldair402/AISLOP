#!/usr/bin/env python3
"""String.toCharArray copia fresca de UTF-16, incluso vacío, surrogados y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class ToCharProbe{public static int run(int n){String[] ss={"","abc","\ud83d\ude00x","\ud83dX\ude00",null};String s=ss[n%5];try{char[] a=s.toCharArray(),b=s.toCharArray();int out=a.length*10+(a!=b?1:0);for(int i=0;i<a.length;i++)out=out*31+a[i];if(a.length>0){a[0]='Q';out=out*31+b[0]+s.charAt(0);}return out;}catch(NullPointerException e){return -1;}}}'''
driver='''import net.minecraft.test.ToCharProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ToCharProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-to-char-') as t:
 d=pathlib.Path(t);(d/'ToCharProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ToCharProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ToCharProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(100));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} copias UTF-16, independencia, identidad de arrays y null')
