#!/usr/bin/env python3
"""Context loader mutable solo en el hilo principal y con cargadores conocidos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ContextSetProbe{public static int run(int n){Thread t=Thread.currentThread();ClassLoader app=ClassLoader.getSystemClassLoader(),p=ClassLoader.getPlatformClassLoader();try{t.setContextClassLoader((n&1)==0?null:p);int v=t.getContextClassLoader()==((n&1)==0?null:p)?1:0;t.setContextClassLoader(app);if(t.getContextClassLoader()==app)v+=2;try{Thread x=null;x.setContextClassLoader(null);}catch(NullPointerException e){v+=4;}return v;}finally{t.setContextClassLoader(app);}}}'''
driver='''import net.minecraft.test.ContextSetProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ContextSetProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-context-set-') as t:
 d=pathlib.Path(t);(d/'ContextSetProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ContextSetProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 env=os.environ.copy();env['MC_AOT_STANDARD_SYSTEM_LOADER']='1';env.pop('MC_AOT_STANDARD_CONTEXT_LOADER',None)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ContextSetProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True,env=env).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} context loaders mutables null/platform/app y NPE; sin suposición del valor inicial')
