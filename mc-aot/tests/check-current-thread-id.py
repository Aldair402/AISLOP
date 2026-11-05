#!/usr/bin/env python3
"""ID del hilo principal proporcionado explícitamente, sin fingir identificadores."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ThreadIdProbe{public static long run(int n){return (n&1)==0?Thread.currentThread().getId():Thread.currentThread().threadId();}public static int nil(int n){try{Thread t=null;return (int)t.getId();}catch(NullPointerException e){return 4;}}}'''
driver='''import net.minecraft.test.ThreadIdProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(ThreadIdProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-thread-id-') as t:
 d=pathlib.Path(t);(d/'ThreadIdProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ThreadIdProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method,desc):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ThreadIdProbe',str(d/method),method,desc],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run','(I)J');seq=list(range(81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;ids=java.splitlines()
 if len(set(ids))!=1 or int(ids[0])<=0:raise AssertionError(ids)
 env=os.environ.copy();env['MC_AOT_JAVA_MAIN_THREAD_ID']=ids[0];native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True,env=env).stdout
 if java!=native:raise AssertionError((java,native))
 for bad in [None,'0','-1','abc']:
  env=os.environ.copy();env.pop('MC_AOT_JAVA_MAIN_THREAD_ID',None)
  if bad is not None:env['MC_AOT_JAVA_MAIN_THREAD_ID']=bad
  p=subprocess.run([str(d/'run'),'0','0'],capture_output=True,text=True,env=env)
  if p.returncode==0 or 'requiere MC_AOT_JAVA_MAIN_THREAD_ID positivo' not in p.stderr:raise AssertionError((bad,p.returncode,p.stderr))
 compile('nil','(I)I');p=subprocess.run([str(d/'nil'),'0','0'],capture_output=True,text=True,check=True)
 if p.stdout!='4\n':raise AssertionError(p.stdout)
 print(f'OK: {len(seq)} ID de hilo actual frente a Java con configuración explícita; null y guardas ausente/incorrecto')
