#!/usr/bin/env python3
"""Diferencial de equivalentes monohilo ConcurrentHashMap y LinkedBlockingQueue."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.Queue;import java.util.concurrent.ConcurrentMap;import java.util.concurrent.ConcurrentHashMap;import java.util.concurrent.LinkedBlockingQueue;
public class CollectionsDemo {
 static ConcurrentMap<String,Object> map=new ConcurrentHashMap<>();static Queue<Object> queue=new LinkedBlockingQueue<>();static Object a=new Object(),b=new Object();static ConcurrentMap<String,Object> missing;
 static Object obj(int n){return n==1?a:n==2?b:null;}
 static int value(Object x){return x==null?0:x==a?1:x==b?2:3;}
 public static int put(String k,int v){return value(map.put(k,obj(v)));}
 public static int absent(String k,int v){return value(map.putIfAbsent(k,obj(v)));}
 public static int get(String k){return value(map.get(k));}
 public static int remove(String k){return value(map.remove(k));}
 public static int contains(String k){return map.containsKey(k)?1:0;}
 public static int size(){return map.size();} public static int empty(){return map.isEmpty()?1:0;}
 public static void clear(){map.clear();}
 public static int offer(int n){return queue.offer(obj(n))?1:0;}
 public static int add(int n){return queue.add(obj(n))?1:0;}
 public static int poll(){return value(queue.poll());}public static int peek(){return value(queue.peek());}
 public static int qsize(){return queue.size();}public static int qempty(){return queue.isEmpty()?1:0;}
 public static void qclear(){queue.clear();}
 public static int missing(){return missing.get("x")==null?0:1;}
 public static int badKey(){return map.get(a)==null?0:1;}
}'''
driver='''import net.minecraft.test.CollectionsDemo;public class CollectionsDriver {
 public static void main(String[] args){for(int i=0;i<args.length;){int op=Integer.parseInt(args[i++]);try{switch(op){
 case 0->System.out.println(CollectionsDemo.put(key(args[i++]),Integer.parseInt(args[i++])));
 case 1->System.out.println(CollectionsDemo.absent(key(args[i++]),Integer.parseInt(args[i++])));
 case 2->System.out.println(CollectionsDemo.get(key(args[i++])));case 3->System.out.println(CollectionsDemo.remove(key(args[i++])));case 4->System.out.println(CollectionsDemo.contains(key(args[i++])));
 case 5->System.out.println(CollectionsDemo.size());case 6->System.out.println(CollectionsDemo.empty());case 7->{CollectionsDemo.clear();System.out.println("OK");}
 case 8->System.out.println(CollectionsDemo.offer(Integer.parseInt(args[i++])));case 9->System.out.println(CollectionsDemo.add(Integer.parseInt(args[i++])));
 case 10->System.out.println(CollectionsDemo.poll());case 11->System.out.println(CollectionsDemo.peek());case 12->System.out.println(CollectionsDemo.qsize());case 13->System.out.println(CollectionsDemo.qempty());case 14->{CollectionsDemo.qclear();System.out.println("OK");}case 15->System.out.println(CollectionsDemo.missing());default->throw new IllegalArgumentException();}}
 catch(Throwable e){System.out.println(e.getClass().getSimpleName());return;}}}
 static String key(String s){return s.equals("<null>")?null:s;}}
'''
with tempfile.TemporaryDirectory(prefix='mc-jdk-collections-') as t:
 d=pathlib.Path(t);(d/'CollectionsDemo.java').write_text(source);(d/'CollectionsDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CollectionsDemo.java'),str(d/'CollectionsDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('put','(Ljava/lang/String;I)I'),('absent','(Ljava/lang/String;I)I'),('get','(Ljava/lang/String;)I'),('remove','(Ljava/lang/String;)I'),('contains','(Ljava/lang/String;)I'),('size','()I'),('empty','()I'),('clear','()V'),('offer','(I)I'),('add','(I)I'),('poll','()I'),('peek','()I'),('qsize','()I'),('qempty','()I'),('qclear','()V'),('missing','()I'),('badKey','()I')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CollectionsDemo',str(d/'native')]
 for n,desc in specs:cmd+=[n,desc]
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(969);javaargs=[];nativeargs=[];keys=['','alpha','βeta','🚀','same','ñ']
 for _ in range(300):
  op=rng.randrange(15);javaargs.append(str(op));nativeargs.append(str(op))
  if op in (0,1,2,3,4):
   key=rng.choice(keys);javaargs.append(key);nativeargs.append('s:'+key)
   if op in (0,1):v=rng.randint(1,2);javaargs.append(str(v));nativeargs.append(str(v))
  elif op in (8,9):v=rng.randint(1,2);javaargs.append(str(v));nativeargs.append(str(v))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'CollectionsDriver',*javaargs],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*nativeargs],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError(next(((i,a,b) for i,(a,b) in enumerate(zip(java.splitlines(),native.splitlines())) if a!=b),('longitud',len(java),len(native))))
 for args,nargs in [(['0','<null>','1'],['0','null','1']),(['0','ok','0'],['0','s:ok','0']),(['2','<null>'],['2','null']),(['8','0'],['8','0']),(['15'],['15'])]:
  j=subprocess.run([str(jdk/'java'),'-cp',str(d),'CollectionsDriver',*args],capture_output=True,text=True,check=True).stdout.strip();n=subprocess.run([str(d/'native'),*nargs],capture_output=True,text=True)
  if j!='NullPointerException' or n.returncode!=2 or 'NullPointerException' not in n.stderr:raise AssertionError((args,j,n.returncode,n.stderr))
 p=subprocess.run([str(d/'native'),'16'],capture_output=True,text=True)
 if p.returncode!=2 or 'clave de ConcurrentHashMap no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 300 operaciones Java de ConcurrentHashMap y LinkedBlockingQueue monohilo; 5 casos null y clave no String rechazada')
