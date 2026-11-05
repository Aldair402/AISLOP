#!/usr/bin/env python3
"""Modifier.isX sobre todas las 4096 combinaciones de bits estándar."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.lang.reflect.Modifier;public class ModifierBitsProbe{public static int run(int n){int v=0;if(Modifier.isPublic(n))v|=1;if(Modifier.isPrivate(n))v|=2;if(Modifier.isProtected(n))v|=4;if(Modifier.isStatic(n))v|=8;if(Modifier.isFinal(n))v|=16;if(Modifier.isSynchronized(n))v|=32;if(Modifier.isVolatile(n))v|=64;if(Modifier.isTransient(n))v|=128;if(Modifier.isNative(n))v|=256;if(Modifier.isInterface(n))v|=512;if(Modifier.isAbstract(n))v|=1024;if(Modifier.isStrict(n))v|=2048;return v;}}'''
driver='''import net.minecraft.test.ModifierBitsProbe;public class Driver{public static void main(String[]a){for(int n=0;n<4096;n++)System.out.println(ModifierBitsProbe.run(n));}}'''
with tempfile.TemporaryDirectory(prefix='mc-modifier-bits-') as t:
 d=pathlib.Path(t);(d/'ModifierBitsProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ModifierBitsProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ModifierBitsProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in range(4096) for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError('Modifier.isX difiere de Java 25')
 print('OK: 4096 combinaciones de doce indicadores Modifier contra Java 25')
