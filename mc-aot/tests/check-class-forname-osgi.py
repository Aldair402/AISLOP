#!/usr/bin/env python3
"""Class.forName de OSGi ausente, solo con classpath cerrado explícito."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class OsgiProbe {
 public static int run(int n){try{String name=n==0?null:"org.osgi.framework.FrameworkUtil";Class.forName(name);return -1;}catch(ClassNotFoundException e){return e.getMessage().equals("org.osgi.framework.FrameworkUtil")?1:2;}catch(NullPointerException e){return 3;}}
 public static int other(int n){try{Class.forName("java.lang.String");return 1;}catch(ClassNotFoundException e){return 2;}}
}'''
other='''package org.osgi.framework;public class FrameworkUtil {}'''
driver='''import net.minecraft.test.OsgiProbe;public class OsgiDriver{public static void main(String[]a){for(String n:a)System.out.println(OsgiProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-osgi-forname-') as temp:
 d=pathlib.Path(temp);(d/'OsgiProbe.java').write_text(source);(d/'OsgiDriver.java').write_text(driver);(d/'FrameworkUtil.java').write_text(other)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'OsgiProbe.java'),str(d/'OsgiDriver.java'),str(d/'FrameworkUtil.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'absent.jar'),'-C',str(d),'net'],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'present.jar'),'-C',str(d),'net','-C',str(d),'org'],check=True)
 base=os.environ.copy();base.pop('MC_AOT_CLOSED_CLASSPATH',None)
 def compile(method,allow=False,archive='absent.jar'):
  env=base.copy()
  if allow:env['MC_AOT_CLOSED_CLASSPATH']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/archive),'net/minecraft/test/OsgiProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,env=env,timeout=120)
 p=compile('run')
 if p.returncode==0 or 'MC_AOT_CLOSED_CLASSPATH=1' not in p.stderr:raise AssertionError(('classpath',p.returncode,p.stderr))
 p=compile('run',True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-20,21))
 # Run Java with only the caller and absent jar: d also contains FrameworkUtil,
 # so copy the driver to an isolated directory without org/.
 clean=d/'driver';clean.mkdir();(clean/'OsgiDriver.class').write_bytes((d/'OsgiDriver.class').read_bytes())
 java=subprocess.run([str(jdk/'java'),'-cp',str(d/'absent.jar')+os.pathsep+str(clean),'OsgiDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'run'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or native.stdout!=java.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('run',True,'present.jar')
 if p.returncode==0 or 'FrameworkUtil presente fuera del perfil' not in p.stderr:raise AssertionError(('clase presente',p.returncode,p.stderr))
 p=compile('other',True)
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'other'),'0','0'],capture_output=True,text=True,timeout=10)
 if native.returncode==0 or 'nombre fuera del perfil verificado' not in native.stderr:raise AssertionError(('otro nombre',native.returncode,native.stderr))
 print(f'OK: {len(vals)} resultados Class.forName OSGi ausente/null frente a Java; guardas de classpath, clase presente y nombre distinto')
