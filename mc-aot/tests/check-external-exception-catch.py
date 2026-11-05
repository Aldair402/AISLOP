#!/usr/bin/env python3
"""Solo jerarquía de catch de biblioteca: sin fingir constructores ni estado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
files={'dep/Foreign.java':'''package dep;public class Foreign extends RuntimeException{int state;public Foreign(String x){super(x);}}''','net/minecraft/test/ForeignCatchDemo.java':'''package net.minecraft.test;public class ForeignCatchDemo{public static int run(int n){try{if(n%2==0)throw new IllegalArgumentException();return n;}catch(dep.Foreign e){return 7;}catch(IllegalArgumentException e){return 8;}}public static int bad(){throw new dep.Foreign("x");}}''','Driver.java':'''import net.minecraft.test.ForeignCatchDemo;public class Driver{public static void main(String[]a){for(String x:a)System.out.println(ForeignCatchDemo.run(Integer.parseInt(x)));}}'''}
with tempfile.TemporaryDirectory(prefix='mc-external-catch-') as t:
 d=pathlib.Path(t)
 for name,src in files.items():
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/n) for n in files]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'dep'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ForeignCatchDemo'];p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 p=subprocess.run(base+[str(d/'bad'),'bad','()I'],capture_output=True,text=True)
 if p.returncode==0 or 'con estado o inicializador' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 80 capturas de jerarquía de biblioteca y rechazo de instancias no soportadas')
