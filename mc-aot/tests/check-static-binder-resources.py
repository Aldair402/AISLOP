#!/usr/bin/env python3
"""Búsqueda cerrada del recurso StaticLoggerBinder; presencia no se oculta."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.io.*;public class ResourceDemo {
 public static int run(int n){try{ClassLoader l=ResourceDemo.class.getClassLoader();switch(n){case 0:return l.getResources("org/slf4j/impl/StaticLoggerBinder.class").hasMoreElements()?1:0;case 1:l.getResources("org/slf4j/impl/StaticLoggerBinder.class").nextElement();return -1;case 2:l.getResources(null);return -1;case 3:ClassLoader x=null;x.getResources("org/slf4j/impl/StaticLoggerBinder.class");return -1;case 4:l.getResources("otra-cosa");return -1;default:return 99;}}catch(NoSuchElementException e){return 102;}catch(NullPointerException e){return 103;}catch(IOException e){return 104;}}
}'''
driver='''import net.minecraft.test.ResourceDemo;public class ResourceDriver{public static void main(String[] a)throws Exception{System.out.println(ClassLoader.getPlatformClassLoader().getResources("org/slf4j/impl/StaticLoggerBinder.class").hasMoreElements()?1:0);for(String s:a)System.out.println(ResourceDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-binder-') as t:
 d=pathlib.Path(t);(d/'ResourceDemo.java').write_text(source);(d/'ResourceDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d/'classes'),str(d/'ResourceDemo.java'),str(d/'ResourceDriver.java')],check=True)
 for present in (False,True):
  jar=d/('present.jar' if present else 'absent.jar')
  with zipfile.ZipFile(jar,'w') as z:
   for f in (d/'classes').rglob('*.class'):z.write(f,str(f.relative_to(d/'classes')))
   if present:z.writestr('org/slf4j/impl/StaticLoggerBinder.class',b'cualquier recurso no vacio')
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(jar),'net/minecraft/test/ResourceDemo',str(d/('present' if present else 'absent')),'run','(I)I'],capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
  java=subprocess.run([str(jdk/'java'),'-cp',str(jar),'ResourceDriver','0'],capture_output=True,text=True,check=True).stdout.splitlines()
  if java!=['0','1' if present else '0']:raise AssertionError(java)
  if present:
   p=subprocess.run([str(d/'present'),'0','0'],capture_output=True,text=True)
   if p.returncode!=2 or 'recursos URL presentes no soportados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
  else:
   java=subprocess.run([str(jdk/'java'),'-cp',str(jar),'ResourceDriver','0','1','2','3'],capture_output=True,text=True,check=True).stdout.splitlines()[1:]
   native=subprocess.run([str(d/'absent'),'0','0','0','1','0','2','0','3'],capture_output=True,text=True,check=True).stdout.splitlines()
   if java!=native:raise AssertionError((java,native))
   p=subprocess.run([str(d/'absent'),'0','4'],capture_output=True,text=True)
   if p.returncode!=2 or 'recurso no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: recurso ausente/URL presentes contra Java 25 y plataforma; cuatro rutas null/vacío coinciden, presencia y otros nombres se rechazan explícitamente')
