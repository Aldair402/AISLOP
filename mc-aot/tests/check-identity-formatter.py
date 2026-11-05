#!/usr/bin/env python3
"""Identidad y singleton del formato ISO_INSTANT sin simular parse/format."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.*;import java.util.function.*;import java.time.format.DateTimeFormatter;
public class IdentityDemo {static DateTimeFormatter fmt=DateTimeFormatter.ISO_INSTANT;
 public static int run(int n){try{switch(n%8){case 0:return Function.identity().apply("foo")=="foo"?1:0;case 1:return Function.identity().apply(null)==null?2:0;case 2:return Function.identity()==Function.identity()?3:0;case 3:return fmt==DateTimeFormatter.ISO_INSTANT?4:0;case 4:return Objects.requireNonNull("x")=="x"?5:0;case 5:Objects.requireNonNull(null);return -1;case 6:return ((Object)Function.identity()) instanceof Function?7:0;default:return fmt==null?0:8;}}catch(NullPointerException e){return 6;}}
 public static int bad(){return fmt.format(null).length();}
}'''
driver='''import net.minecraft.test.IdentityDemo;public class IdentityDriver{public static void main(String[]a){for(String s:a)System.out.println(IdentityDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-identity-') as t:
 d=pathlib.Path(t);(d/'IdentityDemo.java').write_text(src);(d/'IdentityDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'IdentityDemo.java'),str(d/'IdentityDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/IdentityDemo'];p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'IdentityDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[x for n in vals for x in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 p=subprocess.run(base+[str(d/'bad'),'bad','()I'],capture_output=True,text=True)
 if p.returncode==0 or 'no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 80 resultados Function.identity, requireNonNull y singleton ISO_INSTANT; format no soportado')
