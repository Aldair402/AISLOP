#!/usr/bin/env python3
"""Capacidad ArrayList, drainTo y Boolean cacheado frente a Java 25."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.concurrent.*;public class QueueDrainDemo {
 public static int run(int n){try{LinkedBlockingQueue<String> q=new LinkedBlockingQueue<>();q.offer("a");q.offer("b");q.offer("a");switch(n){case 0:case 1:case 2:case 3:case 4:{ArrayList<String>a=new ArrayList<>(n);int x=q.drainTo(a,n);int h=x*1000+q.size()*100+a.size()*10;for(String s:a)h+=s.equals("a")?1:2;return h;}
 case 5:{Set<String>s=new LinkedHashSet<>();s.add("a");int x=q.drainTo(s,2);return x*100+q.size()*10+s.size();}
 case 6:return q.drainTo(null,0);case 7:return q.drainTo(q,0);
 case 8:{Map<String,String>m=new ConcurrentHashMap<>();return q.drainTo(m.values(),3);}
 case 9:{ArrayList<String>a=new ArrayList<>(-1);return a.size();}
 case 10:{Boolean t=Boolean.valueOf(true),f=Boolean.valueOf(false);return (t==Boolean.TRUE?1:0)+(f==Boolean.FALSE?2:0)+(t.booleanValue()?4:0)+(f.booleanValue()?8:0);}
 case 11:{Boolean b=null;return b.booleanValue()?1:0;}
 case 12:{Object o=Boolean.TRUE;return o.getClass().getName().equals("java.lang.Boolean")?12:0;}
 case 13:{ArrayList<String>a=new ArrayList<>(1000001);return a.size();}
 default:return 99;}}catch(NullPointerException e){return 101;}catch(IllegalArgumentException e){return 102;}catch(UnsupportedOperationException e){return 103;}}
}'''
driver='''import net.minecraft.test.QueueDrainDemo;public class QueueDriver{public static void main(String[]a){for(String s:a)System.out.println(QueueDrainDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-queue-drain-') as t:
 d=pathlib.Path(t);(d/'QueueDrainDemo.java').write_text(source);(d/'QueueDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'QueueDrainDemo.java'),str(d/'QueueDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/QueueDrainDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(i) for i in range(13)]*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'QueueDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','13'],capture_output=True,text=True)
 if p.returncode!=2 or 'capacidad experimental excedida' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} resultados Java de drainTo, límites, duplicados, null, identidad y Boolean; capacidad excesiva aborta')
