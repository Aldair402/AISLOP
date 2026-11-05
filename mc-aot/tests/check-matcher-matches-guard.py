#!/usr/bin/env python3
"""Matcher.matches compila, pero no inventa un resultado para el patrón limitado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.regex.*;public class MatchGuard{public static int run(int n){Matcher m=Pattern.compile("([A-Z]*[a-z0-9]+|[A-Z0-9]+)[-._/]?").matcher("abc");if(n==0)return 7;if(n==2)m=null;try{return m.matches()?1:0;}catch(NullPointerException e){return -1;}}}'''
driver='''import net.minecraft.test.MatchGuard;public class Driver{public static void main(String[]a){System.out.println(MatchGuard.run(0));System.out.println(MatchGuard.run(2));}}'''
with tempfile.TemporaryDirectory(prefix='mc-match-guard-') as t:
 d=pathlib.Path(t);(d/'MatchGuard.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MatchGuard.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MatchGuard',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),'0','0','0','2'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True)
 if p.returncode==0 or 'Matcher.matches: operación fuera del perfil implementado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: rama inactiva y null coinciden con Java; matches no nulo aborta explícitamente')
