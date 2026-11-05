#!/usr/bin/env python3
"""HashSet de String/null, sin afirmar orden de iteración general."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.*;public class HSDemo{public static int run(int n){Set<String> s=new HashSet<>();if(n%3==0){s.add("abc");return s.iterator().next().length();}s.add("a");s.add("a");s.add(null);if(n%3==1)return s.size()*10+(s.contains(null)?1:0);s.remove("a");return s.size();}public static int bad(){Set<String> s=new HashSet<>();s.add("a");s.add("b");return s.iterator().next().length();}}'''
driver='''import net.minecraft.test.HSDemo;public class HD{public static void main(String[]a){for(String x:a)System.out.println(HSDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-hashset-') as t:
 d=pathlib.Path(t);(d/'HSDemo.java').write_text(src);(d/'HD.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'HSDemo.java'),str(d/'HD.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/HSDemo',str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(90));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'HD',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'orden no verificado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 90 operaciones HashSet String/null; iteración múltiple aborta por orden no verificado')
