#!/usr/bin/env python3
"""Prioridad de clases multi-release en JARs y bundles, contra el JDK 25."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
version='''package org.example;public class Versioned {public static int value(){return %d;}}'''
app='''package net.minecraft.test; public class App {public static int run(){return org.example.Versioned.value();}}'''
driver='''public class Driver {public static void main(String[] a){System.out.println(net.minecraft.test.App.run());}}'''
with tempfile.TemporaryDirectory(prefix='mc-mr-') as td:
 d=pathlib.Path(td);(d/'Versioned.java').write_text(version%8);(d/'App.java').write_text(app);(d/'Driver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d/'classes'),str(d/'Versioned.java'),str(d/'App.java'),str(d/'Driver.java')],check=True)
 versions={8:(d/'classes/org/example/Versioned.class').read_bytes()}
 for n in (11,25,26):
  (d/'Versioned.java').write_text(version%n);subprocess.run([str(jdk/'javac'),'-d',str(d/f'classes{n}'),str(d/'Versioned.java')],check=True);versions[n]=(d/f'classes{n}/org/example/Versioned.class').read_bytes()
 def make_jar(path,manifest,versionset):
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('META-INF/MANIFEST.MF',manifest);z.write(d/'classes/net/minecraft/test/App.class','net/minecraft/test/App.class');z.write(d/'classes/Driver.class','Driver.class');z.writestr('org/example/Versioned.class',versions[8]);
   for n in versionset:z.writestr(f'META-INF/versions/{n}/org/example/Versioned.class',versions[n])
 def make_bundle(path,jar):
  payload=jar.read_bytes();h=hashlib.sha256(payload).hexdigest()
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('META-INF/versions.list',f'{h}\tversion\tv/v.jar\n');z.writestr('META-INF/versions/v/v.jar',payload);z.writestr('META-INF/libraries.list','')
 cases=[('true',b'Manifest-Version: 1.0\r\nMulti-Release: true\r\n\r\n',[11,25,26],25),('false',b'Manifest-Version: 1.0\r\nMulti-Release: false\r\n\r\n',[11,25],8),('continued',b'Manifest-Version: 1.0\r\nMulti-Release: tr\r\n ue\r\n\r\n',[11,26],8),('continued-marker',b'Manifest-Version: 1.0\r\nMulti-Release: tr\r\n ue\r\nX: Multi-Release: true\r\n\r\n',[11,26],11),('section-only',b'Manifest-Version: 1.0\r\n\r\nName: x\r\nMulti-Release: true\r\n\r\n',[11,25],8)]
 for label,manifest,vset,expected in cases:
  jar=d/(label+'.jar');make_jar(jar,manifest,vset);bundle=d/(label+'-bundle.jar');make_bundle(bundle,jar)
  java=subprocess.run([str(jdk/'java'),'-cp',str(jar),'Driver'],capture_output=True,text=True,check=True).stdout.strip()
  if java!=str(expected):raise AssertionError((label,expected,java))
  for target in (jar,bundle):
   out=d/(target.stem+'-native');p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(target),'net/minecraft/test/App',str(out),'run','()I'],capture_output=True,text=True)
   if p.returncode:raise RuntimeError((label,target,p.stderr))
   native=subprocess.run([str(out),'0'],capture_output=True,text=True,check=True).stdout.strip()
   if native!=java:raise AssertionError((label,target,native,java))
 print('OK: 10 compilaciones de JAR/bundle multi-release; Java 25, versión superior ignorada, manifiesto y continuación coinciden')
