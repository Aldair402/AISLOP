#!/usr/bin/env python3
"""Constructor Java 25 de subclase SecurityManager; contexto de pila bajo guarda."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;@SuppressWarnings("removal") class SM extends SecurityManager {int x;SM(){x=17;}protected Class<?>[] getClassContext(){return super.getClassContext();}} public class SecuritySubDemo{public static int run(int n){SM s=new SM();if(n==0)return s.x;if(n==1)return s.getClassContext().length;return 99;}}'''
driver='''import net.minecraft.test.SecuritySubDemo;public class SecuritySubDriver{public static void main(String[]a){System.out.println(SecuritySubDemo.run(0));}}'''
with tempfile.TemporaryDirectory(prefix='mc-secmgr-sub-') as t:
 d=pathlib.Path(t);(d/'SecuritySubDemo.java').write_text(source);(d/'SecuritySubDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SecuritySubDemo.java'),str(d/'SecuritySubDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SecuritySubDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SecuritySubDriver'],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True)
 if p.returncode!=2 or 'SecurityManager.getClassContext: pila JDK no modelada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: construcción Java 25 de subclase SecurityManager; getClassContext aborta explícitamente')
