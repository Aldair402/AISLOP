#!/usr/bin/env python3
"""Identidad de ClassLoader.getSystemClassLoader en perfil explícito estándar."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class SystemLoaderProbe {public static int run(int n){ClassLoader l=ClassLoader.getSystemClassLoader();ClassLoader p=SystemLoaderProbe.class.getClassLoader();return (l!=null?1:0)+(l==p?2:0)+(l==ClassLoader.getSystemClassLoader()?4:0)+(String.class.getClassLoader()==null?8:0);}}'''
driver='''import net.minecraft.test.SystemLoaderProbe;public class SystemLoaderDriver{public static void main(String[]a){for(String n:a)System.out.println(SystemLoaderProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-system-loader-') as tmp:
 d=pathlib.Path(tmp);(d/'SystemLoaderProbe.java').write_text(source);(d/'SystemLoaderDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SystemLoaderProbe.java'),str(d/'SystemLoaderDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(enabled):
  env=os.environ.copy();env.pop('MC_AOT_STANDARD_SYSTEM_LOADER',None)
  if enabled:env['MC_AOT_STANDARD_SYSTEM_LOADER']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SystemLoaderProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env,timeout=180)
 p=compile(False)
 if p.returncode==0 or 'MC_AOT_STANDARD_SYSTEM_LOADER=1' not in p.stderr:raise AssertionError(('opt-in',p.stderr))
 p=compile(True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SystemLoaderDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 print(f'OK: {len(vals)} identidades del system loader estándar frente a Java; sin opt-in se rechaza; cargadores personalizados no modelados')
