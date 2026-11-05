#!/usr/bin/env python3
"""Despacho seguro para overrides public/protected entre paquetes."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
files={'p/Base.java':'''package p;public abstract class Base {protected abstract int f(int n);public int invoke(int n){return f(n);}}''','q/Child.java':'''package q;public class Child extends p.Base {protected int f(int n){return n*3;}}''','q/Demo.java':'''package q;public class Demo {public static int run(int n){p.Base b=new Child();return b.invoke(n);}}''','D.java':'''import q.Demo;public class D {public static void main(String[]a){for(String x:a)System.out.println(Demo.run(Integer.parseInt(x)));}}'''}
with tempfile.TemporaryDirectory(prefix='mc-cross-public-') as t:
 d=pathlib.Path(t)
 for name,src in files.items():p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/f) for f in files]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'p','-C',str(d),'q'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'q/Demo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'D',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 env={**os.environ,'MC_AOT_DIAGNOSTIC_DISPATCH_PREFIXES':'p/'}
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'q/Demo',str(d/'partial'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'partial'),'0','1'],capture_output=True,text=True)
 if p.returncode==0 or 'tipo o método no precompilado: q/Child' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 80 despachos protected entre paquetes; el modo diagnóstico aborta para clases omitidas')
