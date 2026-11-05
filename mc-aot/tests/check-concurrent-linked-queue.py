#!/usr/bin/env python3
"""Perfil monohilo de ConcurrentLinkedQueue, no garantía de concurrencia."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.Queue;import java.util.concurrent.ConcurrentLinkedQueue;public class QueueDemo{public static int run(int n){Queue<String> q=new ConcurrentLinkedQueue<>();if(n%4==0)return q.poll()==null?10:0;q.add("hi");q.offer("abc");if(n%4==1)return q.size()*100+q.peek().length()*10+q.poll().length();if(n%4==2){q.clear();return q.size();}try{q.add(null);return 1;}catch(NullPointerException e){return 99;}}}'''
driver='''import net.minecraft.test.QueueDemo;public class QueueDriver{public static void main(String[]a){for(String x:a)System.out.println(QueueDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-concurrent-queue-') as t:
 d=pathlib.Path(t);(d/'QueueDemo.java').write_text(src);(d/'QueueDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'QueueDemo.java'),str(d/'QueueDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/QueueDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(120));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'QueueDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 120 operaciones de ConcurrentLinkedQueue en perfil monohilo comparadas con Java')
