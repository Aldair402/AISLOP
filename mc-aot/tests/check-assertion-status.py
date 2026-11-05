#!/usr/bin/env python3
"""Class.desiredAssertionStatus y AssertionError según perfil explícito."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class AssertionDemo {static int x;public static int run(int n){try{switch(n){case 0:return AssertionDemo.class.desiredAssertionStatus()?1:0;case 1:assert false;return 2;case 2:Class<?> c=null;return c.desiredAssertionStatus()?3:0;default:return 99;}}catch(AssertionError e){return 101;}catch(NullPointerException e){return 102;}}}'''
driver='''import net.minecraft.test.AssertionDemo;public class AssertionDriver{public static void main(String[]a){for(String s:a)System.out.println(AssertionDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-assert-') as t:
 d=pathlib.Path(t);(d/'AssertionDemo.java').write_text(source);(d/'AssertionDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'AssertionDemo.java'),str(d/'AssertionDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/AssertionDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 for enabled in (False,True):
  opts=['-ea:net.minecraft.test.AssertionDemo'] if enabled else [];seq=['0','1','2']*10;java=subprocess.run([str(jdk/'java'),*opts,'-cp',str(d),'AssertionDriver',*seq],capture_output=True,text=True,check=True).stdout
  env=dict(os.environ);env.pop('MC_AOT_ASSERTIONS',None)
  if enabled:env['MC_AOT_ASSERTIONS']='net.minecraft.test.AssertionDemo'
  native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True,env=env).stdout
  if java!=native:raise AssertionError((java,native))
 print('OK: 60 resultados Java con assertions activadas/desactivadas, AssertionError y null')
