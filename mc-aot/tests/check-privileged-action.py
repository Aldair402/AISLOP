#!/usr/bin/env python3
"""Despacho de PrivilegedAction.run; no implementa control de privilegios."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.security.PrivilegedAction;
public class PrivilegedActionProbe {
 static int count;static String next(){count++;return "yes";}
 static final class Action implements PrivilegedAction<String>{public String run(){count+=2;return "ok";}}
 public static int run(int n){try{PrivilegedAction<String> a=PrivilegedActionProbe::next;PrivilegedAction<String> b=()->n>0?"plus":"minus";PrivilegedAction<String> c=new Action();PrivilegedAction<String> d=null;return a.run().length()+b.run().length()+c.run().length()+count+(n==42?d.run().length():0);}catch(NullPointerException e){return 100;}}
}'''
driver='''import net.minecraft.test.PrivilegedActionProbe;public class PrivilegedActionDriver{public static void main(String[]a){for(String n:a)System.out.println(PrivilegedActionProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-action-') as tmp:
 d=pathlib.Path(tmp);(d/'PrivilegedActionProbe.java').write_text(source);(d/'PrivilegedActionDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'PrivilegedActionProbe.java'),str(d/'PrivilegedActionDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PrivilegedActionProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-20,61));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'PrivilegedActionDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 print(f'OK: {len(vals)} resultados PrivilegedAction.run con lambdas, capturas, receptor concreto, efectos y null; no es doPrivileged')
