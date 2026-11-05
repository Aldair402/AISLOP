#!/usr/bin/env python3
"""printStackTrace no simulado: null real y error explícito en ruta no implementada."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.io.PrintStream;public class StackGuard {
 public static int run(int n){try{Throwable e=n==0?null:new Exception();PrintStream p=n==1?null:System.err;e.printStackTrace(p);return 0;}catch(NullPointerException e){return 42;}}
}'''
driver='''import net.minecraft.test.StackGuard;public class StackDriver{public static void main(String[] a){System.out.println(StackGuard.run(0));System.out.println(StackGuard.run(1));}}'''
with tempfile.TemporaryDirectory(prefix='mc-stackguard-') as t:
 d=pathlib.Path(t);(d/'StackGuard.java').write_text(source);(d/'StackDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StackGuard.java'),str(d/'StackDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/StackGuard',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'StackDriver'],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),'0','0','0','1'],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','2'],capture_output=True,text=True)
 if p.returncode!=2 or 'stack traces no implementados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: dos casos null coinciden con Java; la impresión no implementada aborta explícitamente sin inventar un stack trace')
