#!/usr/bin/env python3
"""Enumeración vacía solo si el classpath cerrado verifica ausencia del recurso."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class ResourceProbe {
 public static int run(int n){try{ClassLoader l=ResourceProbe.class.getClassLoader();String name=n==0?"META-INF/log4j-provider.properties":n==1?"org/slf4j/impl/StaticLoggerBinder.class":"unrelated";Enumeration<java.net.URL> e=l.getResources(name);if(e.hasMoreElements())return 1;try{e.nextElement();return -1;}catch(NoSuchElementException ok){return 2;}}catch(java.io.IOException e){return 3;}}
}'''
driver='''import net.minecraft.test.ResourceProbe;public class ResourceDriver{public static void main(String[]a){for(String n:a)System.out.println(ResourceProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-provider-resource-') as tmp:
 d=pathlib.Path(tmp);(d/'ResourceProbe.java').write_text(source);(d/'ResourceDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ResourceProbe.java'),str(d/'ResourceDriver.java')],check=True)
 for jar,present in [('absent.jar',False),('present.jar',True)]:
  with zipfile.ZipFile(d/jar,'w') as z:
   for f in (d/'net').rglob('*.class'):z.write(f,f.relative_to(d).as_posix())
   if present:z.writestr('META-INF/log4j-provider.properties',b'present=yes\n')
 def compile(jar,enabled):
  env=os.environ.copy();env.pop('MC_AOT_CLOSED_CLASSPATH',None)
  if enabled:env['MC_AOT_CLOSED_CLASSPATH']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/jar),'net/minecraft/test/ResourceProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env,timeout=180)
 def native(n):return subprocess.run([str(d/'native'),'0',str(n)],capture_output=True,text=True,timeout=30)
 p=compile('absent.jar',True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[0,1]*40;java=subprocess.run([str(jdk/'java'),'-cp',str(d/'absent.jar')+os.pathsep+str(d),'ResourceDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);n=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',str(x))]],capture_output=True,text=True,timeout=30)
 if n.returncode or java.stdout!=n.stdout:raise AssertionError((java.stdout,n.stdout,n.stderr))
 n=native(2)
 if n.returncode==0 or 'recurso no soportado' not in n.stderr:raise AssertionError(('otro recurso',n.stderr))
 for jar,enabled in [('absent.jar',False),('present.jar',True)]:
  p=compile(jar,enabled)
  if p.returncode:raise RuntimeError(p.stderr)
  n=native(0)
  if n.returncode==0 or 'ausencia del proveedor no verificada' not in n.stderr:raise AssertionError((jar,enabled,n.stderr))
 print(f'OK: {len(vals)} enumeraciones ausentes frente a Java; guardas sin opt-in, recurso presente y nombre distinto')
