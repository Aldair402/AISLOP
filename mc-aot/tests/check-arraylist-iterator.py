#!/usr/bin/env python3
"""ArrayList.iterator Java: alias, null, set y modificaciones estructurales."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class ListIteratorDemo {
 public static int run(int n){List<String> list=new ArrayList<>();list.add("a");list.add(null);Iterator<String> i=list.iterator();try{switch(n){
 case 0:return i.hasNext()&&i.next().equals("a")&&i.hasNext()&&i.next()==null&&!i.hasNext()?1:0;
 case 1:i.next();list.set(1,"b");return i.next().equals("b")?2:0;
 case 2:list.add("c");return i.hasNext()?(i.next()==null?0:-1):-2;
 case 3:i.next();i.next();return i.hasNext()?0:(i.next()==null?0:-1);
 case 4:i.next();list.remove(0);return i.hasNext()?0:(i.next()==null?0:-1);
 case 5:list.clear();return !i.hasNext()?(i.next()==null?0:-1):0;
 case 6:Iterator<String> a=list.iterator(),b=list.iterator();return a.next()==b.next()&&a.next()==b.next()?6:0;
 case 7:Iterator<String> z=null;return z.hasNext()?0:1;
 case 8:i.next();i.next();list.remove(0);return i.hasNext()?8:0;
 case 9:list.clear();list.clear();return i.next()==null?0:1;
 default:return 99;
 }}catch(ConcurrentModificationException e){return 101;}catch(NoSuchElementException e){return 102;}catch(NullPointerException e){return 103;}}
}'''
driver='''import net.minecraft.test.ListIteratorDemo;public class ListIterDriver{public static void main(String[] a){for(String s:a)System.out.println(ListIteratorDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-list-iterator-') as t:
 d=pathlib.Path(t);(d/'ListIteratorDemo.java').write_text(source);(d/'ListIterDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ListIteratorDemo.java'),str(d/'ListIterDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ListIteratorDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(10))*10+[-1,10]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ListIterDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)} operaciones Java de iterador ArrayList, set, alias, null, agotamiento y fail-fast')
