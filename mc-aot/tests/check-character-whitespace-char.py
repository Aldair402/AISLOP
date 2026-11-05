#!/usr/bin/env python3
"""Exhaustivo de Character.isWhitespace(char), todas las unidades UTF-16."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class WhitespaceProbe{public static int run(int n){return Character.isWhitespace((char)n)?1:0;}}'''
driver='''import net.minecraft.test.WhitespaceProbe;public class Driver{public static void main(String[]a){for(int n=0;n<65536;n++)System.out.println(WhitespaceProbe.run(n));}}'''
with tempfile.TemporaryDirectory(prefix='mc-whitespace-char-') as t:
 d=pathlib.Path(t);subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'tools/WhitespaceCharJava25.java')],check=True);generated=subprocess.run([str(jdk/'java'),'-cp',str(d),'WhitespaceCharJava25'],capture_output=True,text=True,check=True).stdout
 if generated!=(root/'src/unicode_whitespace_char_java25.inc').read_text():raise AssertionError('tabla no reproducible con Java 25')
 (d/'WhitespaceProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'WhitespaceProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/WhitespaceProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout.splitlines()
 for lo in range(0,65536,4096):
  n=subprocess.run([str(d/'native'),*[v for x in range(lo,lo+4096) for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines()
  if n!=java[lo:lo+4096]:raise AssertionError((lo,next((i for i,(a,b) in enumerate(zip(n,java[lo:lo+4096])) if a!=b),None)))
 print('OK: 65.536 unidades UTF-16 y tabla reproducible de Character.isWhitespace(char) Java 25')
