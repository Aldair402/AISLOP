#!/usr/bin/env python3
"""Collections.emptyList/emptyMap: singleton, lecturas y excepciones."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.*;public class EmptyCollectionsDemo {static Map<String,String> m=Collections.emptyMap();static List<String> l=Collections.emptyList();
 public static int run(int n){try{switch(n%14){case 0:return m==Collections.<String,String>emptyMap()?1:0;case 1:return m.get(null)==null?2:0;case 2:return m.remove(null)==null?3:0;case 3:m.clear();return m.size();case 4:m.put(null,null);return -1;case 5:m.computeIfAbsent(null,null);return -1;case 6:return l==Collections.<String>emptyList()?6:0;case 7:return l.size();case 8:l.clear();return 8;case 9:l.add("x");return -1;case 10:l.get(0);return -1;case 11:l.set(0,"x");return -1;case 12:return l.iterator().hasNext()?0:12;default:l.iterator().next();return -1;}}catch(UnsupportedOperationException e){return 77;}catch(IndexOutOfBoundsException e){return 88;}catch(NoSuchElementException e){return 99;}}
}'''
driver='''import net.minecraft.test.EmptyCollectionsDemo;public class EmptyDriver{public static void main(String[]a){for(String x:a)System.out.println(EmptyCollectionsDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-empty-collections-') as t:
 d=pathlib.Path(t);(d/'EmptyCollectionsDemo.java').write_text(src);(d/'EmptyDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EmptyCollectionsDemo.java'),str(d/'EmptyDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EmptyCollectionsDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(140));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'EmptyDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 print('OK: 140 operaciones Java de Collections.emptyList/emptyMap, identidad e inmutabilidad')
