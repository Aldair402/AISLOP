#!/usr/bin/env python3
"""Traduce un main(String[]) sintético y lo compara byte a byte con la JVM."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;
public class MainFixture {
 static int count(String[] a){return a.length;}
 static int alias(String a){String[] b=new String[2];b[0]=a;b[1]="Mundo";return b[0]==a && b[1].equals("Mundo")?b[1].length():-1;}
 public static void main(String[] args){
  System.out.println("Inicio");
  System.out.println(count(args));
  System.out.println((String)null);
  System.out.println("isolado:\uD800");
  if(args.length>0){
   String s=args[0];System.out.println(s);System.out.println(s.length());
   if(s.length()>0)System.out.println((int)s.charAt(0));
   System.out.println(s.equals("🚀"));System.out.println(alias(s));
  }
  if(args.length>1)System.out.println(args[1]);
 }
}'''
with tempfile.TemporaryDirectory(prefix='mc-string-main-') as tmp:
 d=pathlib.Path(tmp);(d/'MainFixture.java').write_text(source,encoding='utf8')
 subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-d',str(d),str(d/'MainFixture.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'fixture.jar'),'net/minecraft/test/MainFixture','main','([Ljava/lang/String;)V',str(d/'native')],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 cases=[[],[''],['🚀'],['Árbol','村'],['null','line\nbreak'],['abc','abc','extra']]
 for args in cases:
  java=subprocess.run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.MainFixture',*args],capture_output=True,check=True)
  native=subprocess.run([str(d/'native'),*args],capture_output=True,check=True)
  if java.stdout!=native.stdout:raise AssertionError((args,java.stdout,native.stdout,java.stderr,native.stderr))
 print(f'OK: main(String[]) sintético; {len(cases)} ejecuciones coinciden byte a byte con Java 25, incluyendo UTF-16, null, array y stdout')
