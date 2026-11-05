#!/usr/bin/env python3
"""Cadena app → platform → bootstrap/null en perfil explícito estándar."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ParentProbe{public static int run(int n){try{ClassLoader a=ClassLoader.getSystemClassLoader(),p=a.getParent(),q=ClassLoader.getPlatformClassLoader();ClassLoader[] arr={p};int x=(p==q?1:0)+(p!=a?2:0)+(p.getParent()==null?4:0)+(p==a.getParent()?8:0)+(arr[0] instanceof ClassLoader?16:0);if((n&1)!=0){ClassLoader z=null;z.getParent();}return x;}catch(NullPointerException e){return 64;}}}'''
driver='''import net.minecraft.test.ParentProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ParentProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-classloader-parent-') as t:
 d=pathlib.Path(t);(d/'ParentProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ParentProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(enabled):
  env=os.environ.copy();env.pop('MC_AOT_STANDARD_SYSTEM_LOADER',None)
  if enabled:env['MC_AOT_STANDARD_SYSTEM_LOADER']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ParentProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180,env=env)
 p=compile(False)
 if p.returncode==0 or 'MC_AOT_STANDARD_SYSTEM_LOADER=1' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile(True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} identidades de app/platform/bootstrap, null y ClassLoader[]; opt-in obligatorio')
