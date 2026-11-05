#!/usr/bin/env python3
"""ContextClassLoader principal solo bajo supuesto explícito de cargador estándar."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ContextLoaderProbe{public static int run(int n){try{Thread t=(n&1)==0?null:Thread.currentThread();ClassLoader c=t.getContextClassLoader();return (c==ClassLoader.getSystemClassLoader()?1:0)+(c==t.getContextClassLoader()?2:0)+(c==ContextLoaderProbe.class.getClassLoader()?4:0);}catch(NullPointerException e){return 10;}}}'''
driver='''import net.minecraft.test.ContextLoaderProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ContextLoaderProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-context-loader-') as t:
 d=pathlib.Path(t);(d/'ContextLoaderProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ContextLoaderProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 env=os.environ.copy();env['MC_AOT_STANDARD_SYSTEM_LOADER']='1';p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ContextLoaderProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;env['MC_AOT_STANDARD_CONTEXT_LOADER']='1';n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True,env=env).stdout
 if j!=n:raise AssertionError((j,n))
 env.pop('MC_AOT_STANDARD_CONTEXT_LOADER');p=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True,env=env)
 if p.returncode==0 or 'requiere MC_AOT_STANDARD_CONTEXT_LOADER=1' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados del cargador de contexto principal estándar, identidad/null y guarda de supuesto')
