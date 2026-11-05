#!/usr/bin/env python3
"""String.lastIndexOf(String) con UTF-16, surrogados y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class LastIndexProbe{public static int run(int n){String[] h={"","abcabc","\ud83d\ude00x\ud83d\ude00","aaaaa","\ud83dX\ude00",null};String[] q={"","abc","bc","aa","\ud83d","\ude00","\ud83d\ude00","X","z",null};try{return h[n/10].lastIndexOf(q[n%10]);}catch(NullPointerException e){return -5;}}}'''
driver='''import net.minecraft.test.LastIndexProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(LastIndexProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-last-index-') as t:
 d=pathlib.Path(t);(d/'LastIndexProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LastIndexProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LastIndexProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(60));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados String.lastIndexOf(String) con UTF-16, surrogados y null')
