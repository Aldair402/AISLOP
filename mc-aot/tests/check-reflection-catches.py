#!/usr/bin/env python3
"""Tipos catch para excepciones reflectivas, sin afirmar soporte de reflexión."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.lang.reflect.InvocationTargetException;
public class ReflectionCatch {
 static void noop()throws InvocationTargetException {}
 public static int run(int n){try {switch(n){case 0:throw new ClassNotFoundException();case 1:throw new NoSuchMethodException();case 2:throw new InstantiationException();case 3:throw new IllegalAccessException();case 4:throw new ReflectiveOperationException();case 5:noop();return 55;default:throw new IllegalArgumentException();}}
  catch(ClassNotFoundException e){return 10;}catch(InvocationTargetException e){return 20;}catch(ReflectiveOperationException e){return 30;}catch(Exception e){return 40;}}
}'''
driver='''import net.minecraft.test.ReflectionCatch;public class ReflectionDriver{public static void main(String[] a){for(String s:a)System.out.println(ReflectionCatch.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-reflection-catches-') as t:
 d=pathlib.Path(t);(d/'ReflectionCatch.java').write_text(source);(d/'ReflectionDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ReflectionCatch.java'),str(d/'ReflectionDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ReflectionCatch',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['-1','0','1','2','3','4','5','6'];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ReflectionDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native or java!='40\n10\n30\n30\n30\n30\n55\n40\n':raise AssertionError((java,native))
 print('OK: 8 resultados con excepciones reflectivas y orden de catch Java; reflexión no implementada')
