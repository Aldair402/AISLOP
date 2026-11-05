#!/usr/bin/env python3
"""Perfil explícito de procesadores, ProcessHandle, AtomicInteger y operaciones matemáticas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.concurrent.atomic.AtomicInteger;public class RuntimeDemo{public static int run(int n){AtomicInteger a=new AtomicInteger(Integer.MAX_VALUE);switch(n%11){case 0:return Runtime.getRuntime().availableProcessors();case 1:return Runtime.getRuntime()==Runtime.getRuntime()?1:0;case 2:return ProcessHandle.current()==ProcessHandle.current()?2:0;case 3:return ProcessHandle.current().pid()>0?3:0;case 4:return Long.toString(-1234567890123L).length();case 5:return a.getAndIncrement();case 6:return a.incrementAndGet();case 7:return a.compareAndSet(Integer.MAX_VALUE,-5)?a.get():0;case 8:return Long.numberOfLeadingZeros(1L<<n%63);case 9:return (int)Math.ceil(-3.3);default:return (int)Math.sqrt(144);}}}'''
driver='''import net.minecraft.test.RuntimeDemo;public class RuntimeDriver{public static void main(String[]a){for(String x:a)System.out.println(RuntimeDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-runtime-profile-') as t:
 d=pathlib.Path(t);(d/'RuntimeDemo.java').write_text(src);(d/'RuntimeDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RuntimeDemo.java'),str(d/'RuntimeDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RuntimeDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(110));j=subprocess.run([str(jdk/'java'),'-XX:ActiveProcessorCount=3','-cp',str(d),'RuntimeDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;env=os.environ.copy();env['MC_AOT_JAVA_PROCESSORS']='3';a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],env=env,capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 env.pop('MC_AOT_JAVA_PROCESSORS');p=subprocess.run([str(d/'native'),'0','0'],env=env,capture_output=True,text=True)
 if p.returncode==0 or 'MC_AOT_JAVA_PROCESSORS' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 110 operaciones con perfil de procesadores explícito, ProcessHandle y AtomicInteger; guarda sin configuración')
