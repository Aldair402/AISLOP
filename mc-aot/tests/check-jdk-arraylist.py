#!/usr/bin/env python3
"""ArrayList por referencias y null, sin iteradores ni equals arbitrario."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.*;
public class ListDemo {static List<Object> list=new ArrayList<>();static Collection<Object> alias=list;static Object a=new Object(),b=new Object();
 static Object value(int x){return x==0?null:x==1?a:b;}static int id(Object x){return x==null?0:x==a?1:x==b?2:3;}
 public static int add(int v){return alias.add(value(v))?1:0;}public static int get(int i){return id(list.get(i));}public static int set(int i,int v){return id(list.set(i,value(v)));}public static int remove(int i){return id(list.remove(i));}public static int size(){return alias.size();}public static int empty(){return alias.isEmpty()?1:0;}public static void clear(){alias.clear();}}
'''
driver='''import net.minecraft.test.ListDemo;public class ListDriver{public static void main(String[] a){for(int i=0;i<a.length;){int op=Integer.parseInt(a[i++]);switch(op){case 0->System.out.println(ListDemo.add(Integer.parseInt(a[i++])));case 1->System.out.println(ListDemo.get(Integer.parseInt(a[i++])));case 2->System.out.println(ListDemo.set(Integer.parseInt(a[i++]),Integer.parseInt(a[i++])));case 3->System.out.println(ListDemo.remove(Integer.parseInt(a[i++])));case 4->System.out.println(ListDemo.size());case 5->System.out.println(ListDemo.empty());case 6->{ListDemo.clear();System.out.println("OK");}}}}}'''
with tempfile.TemporaryDirectory(prefix='mc-arraylist-') as t:
 d=pathlib.Path(t);(d/'ListDemo.java').write_text(source);(d/'ListDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ListDemo.java'),str(d/'ListDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ListDemo',str(d/'native'),'add','(I)I','get','(I)I','set','(II)I','remove','(I)I','size','()I','empty','()I','clear','()V'];p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(414);args=[];length=0
 for _ in range(300):
  op=rng.randrange(7)
  if length==0 and op in (1,2,3):op=0
  args.append(str(op))
  if op==0:args.append(str(rng.randrange(3)));length+=1
  elif op in (1,2,3):
   args.append(str(rng.randrange(length)))
   if op==2:args.append(str(rng.randrange(3)))
   if op==3:length-=1
  elif op==6:length=0
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ListDriver',*args],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:300],native[:300]))
 for n in [-1,0,2147483647]:
  p=subprocess.run([str(d/'native'),'1',str(n)],capture_output=True,text=True)
  if p.returncode!=2 or 'IndexOutOfBoundsException' not in p.stderr:raise AssertionError((n,p.stderr))
 print('OK: 300 operaciones ArrayList Java con alias, mutaciones, null y 3 índices inválidos por categoría')
