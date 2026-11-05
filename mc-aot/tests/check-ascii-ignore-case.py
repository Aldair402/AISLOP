#!/usr/bin/env python3
"""Casos ASCII, Unicode, null y límites de equalsIgnoreCase."""
import os,pathlib,random,string,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class IgnoreCase {public static int eq(String a,String b){return a.equalsIgnoreCase(b)?1:0;}}'''
driver='''import net.minecraft.test.IgnoreCase;public class IgnoreCaseDriver{public static void main(String[] a){for(int i=0;i<a.length;i+=2)System.out.println(IgnoreCase.eq(a[i],a[i+1]));}}'''
with tempfile.TemporaryDirectory(prefix='mc-ascii-case-') as t:
 d=pathlib.Path(t);(d/'IgnoreCase.java').write_text(source);(d/'IgnoreCaseDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'IgnoreCase.java'),str(d/'IgnoreCaseDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/IgnoreCase',str(d/'native'),'eq','(Ljava/lang/String;Ljava/lang/String;)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(104);chars=string.ascii_letters+string.digits+'_-@';pairs=[('',''),('true','TRUE'),('false','FaLsE'),('A','a'),('x','')]
 for i in range(200):
  s=''.join(rng.choice(chars) for _ in range(rng.randrange(10)));v=''.join(c.swapcase() if rng.randrange(2) else c for c in s) if i%2 else ''.join(rng.choice(chars) for _ in range(rng.randrange(10)));pairs.append((s,v))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'IgnoreCaseDriver',*[x for pair in pairs for x in pair]],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*[x for a,b in pairs for x in ('0','s:'+a,'s:'+b)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:200],native[:200]))
 p=subprocess.run([str(d/'native'),'0','s:a','null'],capture_output=True,text=True,check=True)
 if p.stdout!='0\n':raise AssertionError(p.stdout)
 for args,error in [(['0','null','s:x'],'NullPointerException')]:
  p=subprocess.run([str(d/'native'),*args],capture_output=True,text=True)
  if p.returncode!=2 or error not in p.stderr:raise AssertionError((args,p.returncode,p.stderr))
 p=subprocess.run([str(d/'native'),'0','s:İ','s:i'],capture_output=True,text=True,check=True)
 if p.stdout!='1\n':raise AssertionError(p.stdout)
 print(f'OK: {len(pairs)} comparaciones ASCII Java, null y comparación Unicode representativa')
