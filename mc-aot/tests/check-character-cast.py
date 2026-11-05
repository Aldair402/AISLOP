#!/usr/bin/env python3
"""Casts Character y caché Java para unidades ASCII y no ASCII."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class CharCastBox{public static int run(int n){try{Object x=n%3==0?null:n%3==1?Character.valueOf((char)n):"x";boolean test=x instanceof Character;Character c=(Character)x;if(c==null)return test?9:1;return (test?2:0)+(c==Character.valueOf((char)n)?4:0)+c.charValue()*8;}catch(ClassCastException e){return 7;}}}'''
driver='''import net.minecraft.test.CharCastBox;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(CharCastBox.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-char-box-cast-') as t:
 d=pathlib.Path(t);(d/'CharCastBox.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CharCastBox.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CharCastBox',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-120,240));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Character valueOf/cast/caché/null frente a Java')
