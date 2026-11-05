#!/usr/bin/env python3
"""Java 25 deshabilita el SecurityManager: get es null, set siempre lanza UOE."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;@SuppressWarnings("removal") public class SecurityDemo {public static int run(int n){try{if(n==0)return System.getSecurityManager()==null?1:0;System.setSecurityManager(null);return -1;}catch(UnsupportedOperationException e){return 2;}}}'''
driver='''import net.minecraft.test.SecurityDemo;public class SecurityDriver{public static void main(String[] a){for(String x:a)System.out.println(SecurityDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-security-') as t:
 d=pathlib.Path(t);(d/'SecurityDemo.java').write_text(source);(d/'SecurityDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SecurityDemo.java'),str(d/'SecurityDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SecurityDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['0','1','2']*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SecurityDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print('OK: 30 operaciones Java 25 de getSecurityManager y setSecurityManager(null)')
