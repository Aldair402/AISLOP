#!/usr/bin/env python3
"""Arrays.sort(char[]) por unidades unsigned UTF-16, con duplicados y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.Arrays;public class SortCharProbe{public static int run(int n){if(n%17==0){try{Arrays.sort((char[])null);}catch(NullPointerException e){return -7;}}char[] a=new char[n%97];int x=n;for(int i=0;i<a.length;i++){x=x*1664525+1013904223;a[i]=(char)(x>>>16);}Arrays.sort(a);int h=1;for(int i=0;i<a.length;i++)h=31*h+a[i];return h;}}'''
driver='''import net.minecraft.test.SortCharProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(SortCharProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-sort-char-') as t:
 d=pathlib.Path(t);(d/'SortCharProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SortCharProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SortCharProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(350));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} arrays sort(char[]) aleatorios, extremos de UTF-16 y null frente a Java')
