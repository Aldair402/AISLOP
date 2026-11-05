#!/usr/bin/env python3
"""Rechazo conservador del despacho virtual de jerarquías entre paquetes."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
files={'p/Base.java':'''package p;public class Base {int f(){return 3;}public int invoke(){return f();}}''','q/Child.java':'''package q;public class Child extends p.Base {public int f(){return 9;}}''','q/Demo.java':'''package q;public class Demo {public static int run(){return new Child().invoke();}}'''}
with tempfile.TemporaryDirectory(prefix='mc-cross-dispatch-') as t:
 d=pathlib.Path(t)
 for name,src in files.items():
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/f) for f in files]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'p','-C',str(d),'q'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'q/Demo',str(d/'native'),'run','()I'],capture_output=True,text=True)
 if p.returncode==0 or 'despacho virtual entre paquetes no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: override package-private ambiguo entre paquetes se rechaza, sin despacho incorrecto')
