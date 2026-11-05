#!/usr/bin/env python3
"""La representación decimal Java de double no se sustituye por formato Rust."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class DoubleGuard{public static int run(int n){StringBuilder b=new StringBuilder();if(n==0)return 7;return b.append(1.25).length();}}'''
driver='''import net.minecraft.test.DoubleGuard;public class Driver{public static void main(String[]a){System.out.println(DoubleGuard.run(0));}}'''
with tempfile.TemporaryDirectory(prefix='mc-double-guard-') as t:
 d=pathlib.Path(t);(d/'DoubleGuard.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DoubleGuard.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DoubleGuard',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True)
 if p.returncode==0 or 'StringBuilder.append(double): representación decimal no implementada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: rama sin append(double) coincide con Java; formato double aborta explícitamente')
