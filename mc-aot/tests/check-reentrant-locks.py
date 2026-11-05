#!/usr/bin/env python3
"""ReentrantLock y read/write locks en ejecución monohilo; upgrade aborta."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.concurrent.locks.*;public class LockDemo{public static int run(int n){try{if(n%6==5){Lock l=new ReentrantLock();try{l.lockInterruptibly();}catch(InterruptedException e){return -5;}l.unlock();return 5;}if(n%6==0){ReentrantLock l=new ReentrantLock();l.lock();l.lock();int c=l.getHoldCount();l.unlock();l.unlock();return c;}if(n%6==1){ReentrantLock l=new ReentrantLock();l.unlock();}if(n%6==2){ReadWriteLock rw=new ReentrantReadWriteLock();Lock r=rw.readLock(),w=rw.writeLock();w.lock();r.lock();w.unlock();r.unlock();return 2;}if(n%6==3){ReadWriteLock rw=new ReentrantReadWriteLock();return rw.readLock()==rw.readLock()&&rw.writeLock()==rw.writeLock()?3:0;}ReadWriteLock rw=new ReentrantReadWriteLock();rw.readLock().unlock();return -1;}catch(IllegalMonitorStateException e){return 77;}}public static int bad(){ReadWriteLock rw=new ReentrantReadWriteLock();rw.readLock().lock();rw.writeLock().lock();return 1;}}'''
driver='''import net.minecraft.test.LockDemo;public class LockDriver{public static void main(String[]a){for(String x:a)System.out.println(LockDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-locks-') as t:
 d=pathlib.Path(t);(d/'LockDemo.java').write_text(src);(d/'LockDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LockDemo.java'),str(d/'LockDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LockDemo',str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(100));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'LockDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'upgrade bloquearía' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 100 operaciones de locks monohilo; upgrade bloqueante aborta explícitamente')
