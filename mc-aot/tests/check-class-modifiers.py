#!/usr/bin/env python3
"""Class.getModifiers: ClassFile e InnerClasses, incluidos miembros anidados."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ClassModsProbe{
 static class Pkg{} public static final class Pub{} private class Private{} protected interface Nested{} enum E{A} interface Other{}
 public static int run(int n){Class<?> c=n%8==0?ClassModsProbe.class:n%8==1?Pkg.class:n%8==2?Pub.class:n%8==3?Private.class:n%8==4?Nested.class:n%8==5?E.class:n%8==6?Other.class:null;try{return c.getModifiers();}catch(NullPointerException e){return -7;}}
 public static int unsupported(int n){return String.class.getModifiers();}
}'''
driver='''import net.minecraft.test.ClassModsProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ClassModsProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-class-mods-') as t:
 d=pathlib.Path(t);(d/'ClassModsProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ClassModsProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 for m in ('run','unsupported'):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ClassModsProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((m,p.stderr))
 seq=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError([(i,a,b) for i,(a,b) in enumerate(zip(j.splitlines(),n.splitlines())) if a!=b][:12])
 p=subprocess.run([str(d/'unsupported'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Class.getModifiers: clase fuera del registro' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} modificadores top-level/anidadas/interfaces/enum y null; JDK no registrada aborta')
