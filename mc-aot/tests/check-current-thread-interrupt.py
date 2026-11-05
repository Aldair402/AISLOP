#!/usr/bin/env python3
"""Perfil monohilo Thread.currentThread e interrupción, sin esperas ni hilos nuevos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.concurrent.locks.*;public class ThreadProbe{public static int run(int n){Thread.interrupted();Thread t=Thread.currentThread();int r=t==Thread.currentThread()?1:0;if((n&1)!=0)t.interrupt();if(t.isInterrupted())r+=2;if((n&2)!=0)t.interrupt();if(Thread.interrupted())r+=4;if(t.isInterrupted())r+=8;if(Thread.interrupted())r+=16;try{Thread x=null;if((n&4)!=0)x.interrupt();else x.isInterrupted();return -1;}catch(NullPointerException e){return r+32;}}public static int name(int n){Thread t=Thread.currentThread();int v=t.getName().equals("main")?1:0;v+=t.getName()==t.getName()?2:0;v+=t.getName()=="main"?4:0;try{t.setName(null);return -1;}catch(NullPointerException e){return v+(e.getMessage().equals("name cannot be null")?8:16);}}public static int rename(int n){Thread.currentThread().setName("changed");return 0;}public static int lock(int n){Thread.interrupted();ReadWriteLock rw=new ReentrantReadWriteLock();Lock l=(n%3==0)?new ReentrantLock():(n%3==1)?rw.readLock():rw.writeLock();if((n&1)!=0)Thread.currentThread().interrupt();try{l.lockInterruptibly();l.unlock();return Thread.interrupted()?1:2;}catch(InterruptedException e){return Thread.currentThread().isInterrupted()?3:4;}}}
'''
driver='''import net.minecraft.test.ThreadProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(n.startsWith("l")?ThreadProbe.lock(Integer.parseInt(n.substring(1))):n.startsWith("n")?ThreadProbe.name(Integer.parseInt(n.substring(1))):ThreadProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-thread-current-') as t:
 d=pathlib.Path(t);(d/'ThreadProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ThreadProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ThreadProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ThreadProbe',str(d/'lock'),'lock','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 nums=list(range(60));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*[f'l{n}' for n in nums]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'lock'),*[v for n in nums for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError(('lock',java,native))
 for method in ['name','rename']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ThreadProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
  p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if method=='name':
   oracle=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver','n0'],capture_output=True,text=True,check=True).stdout
   if p.returncode or p.stdout!=oracle:raise AssertionError((method,p.returncode,p.stdout,oracle,p.stderr))
  if method=='rename' and (p.returncode==0 or 'Thread.setName: cambio de nombre no soportado' not in p.stderr):raise AssertionError((method,p.returncode,p.stderr))
 print(f'OK: {len(seq)+len(nums)+1} resultados identidad, nombre, interrupción, limpieza, null y lockInterruptibly; renombrado aborta')
