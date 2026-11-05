#!/usr/bin/env python3
"""defaultThreadFactory: rama inactiva permitida, ejecución no simula hilos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.concurrent.Executors;public class FactoryGuard{public static int run(int n){if(n==0)return 7;return Executors.defaultThreadFactory()==null?0:1;}}'''
driver='''import net.minecraft.test.FactoryGuard;public class Driver{public static void main(String[]a){System.out.println(FactoryGuard.run(0));}}'''
with tempfile.TemporaryDirectory(prefix='mc-factory-guard-') as t:
 d=pathlib.Path(t);(d/'FactoryGuard.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FactoryGuard.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FactoryGuard',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True)
 if p.returncode==0 or 'Executors.defaultThreadFactory: hilos no implementados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: rama inactiva coincide con Java; defaultThreadFactory aborta sin simular hilos')
