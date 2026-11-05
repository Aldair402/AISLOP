#!/usr/bin/env python3
"""ConstantValue String observado por getstatic durante inicialización circular."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
stub='''package net.minecraft.test; public class ConstantOwner {public static String CONST; public static int check(){return 0;}}'''
use=r'''package net.minecraft.test;
public class ConstantUser {
 static int observed=(ConstantOwner.CONST=="🚀\uD800"?10000:0)+ConstantOwner.CONST.length()*100+ConstantOwner.CONST.charAt(2);
 public static int check(){return observed;}
}'''
real=r'''package net.minecraft.test;
public class ConstantOwner {
 public static final String CONST="🚀\uD800";
 static int observed=ConstantUser.check();
 public static int check(){return observed;}
}'''
driver='''import net.minecraft.test.ConstantOwner; public class ConstantDriver {public static void main(String[] args){System.out.println(ConstantOwner.check());}}'''
with tempfile.TemporaryDirectory(prefix='mc-static-string-constant-') as t:
 d=pathlib.Path(t);(d/'ConstantOwner.java').write_text(stub);(d/'ConstantUser.java').write_text(use,encoding='utf8')
 subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-d',str(d),str(d/'ConstantOwner.java'),str(d/'ConstantUser.java')],check=True)
 (d/'ConstantOwner.java').write_text(real,encoding='utf8');(d/'ConstantDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-cp',str(d),'-d',str(d),str(d/'ConstantOwner.java'),str(d/'ConstantDriver.java')],check=True)
 # The client was compiled against the non-final stub: the bytecode contains getstatic.
 dis=subprocess.run([str(jdk/'javap'),'-c','-p','-cp',str(d),'net.minecraft.test.ConstantUser'],capture_output=True,text=True,check=True).stdout
 if 'getstatic' not in dis or 'ConstantOwner.CONST' not in dis:raise AssertionError(dis)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ConstantOwner',str(d/'native'),'check','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ConstantDriver'],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),'0'],capture_output=True,text=True,check=True).stdout
 if java!=native or java.strip()!=str(10000+300+0xd800):raise AssertionError((java,native))
 print('OK: ConstantValue String se interna antes del <clinit>; getstatic circular observa identidad y unidades UTF-16, incluido sustituto aislado')
