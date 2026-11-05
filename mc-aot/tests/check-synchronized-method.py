#!/usr/bin/env python3
"""Métodos de instancia synchronized, reentrada y excepciones en monohilo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;class Sync {int v; synchronized int add(int n){if(!Thread.holdsLock(this))return -999;synchronized(this){v+=n;if(n%3==0)throw new IllegalArgumentException();return v;}}synchronized int recur(int n){return n==0?v:1+recur(n-1);}}public class SyncDemo{public static int run(int n){Sync s=new Sync();try{s.add(n);}catch(IllegalArgumentException e){s.add(1);}return s.recur(n%5)+(Thread.holdsLock(s)?10000:0);}}'''
driver='''import net.minecraft.test.SyncDemo;public class SyncDriver{public static void main(String[]a){for(String x:a)System.out.println(SyncDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-sync-method-') as t:
 d=pathlib.Path(t);(d/'SyncDemo.java').write_text(src);(d/'SyncDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SyncDemo.java'),str(d/'SyncDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SyncDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(120));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'SyncDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 120 llamadas synchronized monohilo con reentrada y excepciones')
