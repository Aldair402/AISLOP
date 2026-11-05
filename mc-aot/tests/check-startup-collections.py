#!/usr/bin/env python3
"""Colecciones inmutables, orden y fail-fast sobre TreeMap y ArrayList."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.*;public class CollectionExtDemo{public static int run(int n){try{switch(n%20){
case 0:return List.of("a","b","c","d","e","f","g","h").get(7).charAt(0);
case 1:String[] src={"a","b"};List<String> l=List.of(src);src[0]="z";return l.get(0).charAt(0);
case 2:List.of("x",null);return -1;
case 3:List.of().clear();return -1;
case 4:List.of().addAll(Collections.emptyList());return -1;
case 5:ArrayList<String> l2=new ArrayList<>();l2.add("b");l2.add("a");l2.addAll(l2);Collections.sort(l2);return l2.get(1).charAt(0)*10+l2.size();
case 6:ArrayList<String> l3=new ArrayList<>();l3.add("a");Iterator<String> it=l3.iterator();l3.addAll(Collections.emptyList());it.next();return -1;
case 7:TreeMap<Character,String> m=new TreeMap<>();m.put('z',"z");m.put('a',"a");return m.values().iterator().next().charAt(0);
case 8:TreeMap<Character,String> m2=new TreeMap<>();m2.put('a',null);return m2.containsKey('a')?8:0;
case 9:new TreeMap<Character,String>().get(null);return -1;
case 10:TreeMap<Character,String> m3=new TreeMap<>();m3.put('a',"a");Iterator<String> i=m3.values().iterator();m3.clear();return i.hasNext()?10:0;
case 11:TreeMap<Character,String> m4=new TreeMap<>();m4.put('a',"a");Iterator<String> i2=m4.values().iterator();m4.clear();i2.next();return -1;
case 12:TreeMap<Character,String> m5=new TreeMap<>();m5.put('a',"a");Map.Entry<Character,String> e=m5.entrySet().iterator().next();m5.put('a',"b");return e.getValue().charAt(0);
case 13:Collections.<String>emptyList().addAll(Collections.emptyList());return 13;
case 14:return List.of()==List.of()?14:0;
case 15:LinkedHashMap<String,String> lm=new LinkedHashMap<>();lm.put("z","z");lm.put("a","a");return lm.values().iterator().next().charAt(0);
case 16:LinkedHashMap<String,String> lm1=new LinkedHashMap<>();lm1.put(null,null);return lm1.containsKey(null)?16:0;
case 17:LinkedHashMap<String,String> lm2=new LinkedHashMap<>();lm2.put("x","a");Iterator<String> ii=lm2.values().iterator();lm2.put("y","b");ii.next();return -1;
case 18:LinkedHashMap<String,String> lm3=new LinkedHashMap<>();lm3.put("x","a");lm3.put("y","b");lm3.remove("x");lm3.put("x","c");return lm3.values().iterator().next().charAt(0);
default:TreeMap<Character,String> empty=new TreeMap<>();Iterator<String> ei=empty.values().iterator();empty.put('x',"x");ei.next();return -1;
}}catch(NoSuchElementException e){return 74;}catch(NullPointerException e){return 71;}catch(UnsupportedOperationException e){return 72;}catch(ConcurrentModificationException e){return 73;}}}'''
driver='''import net.minecraft.test.CollectionExtDemo;public class CDriver{public static void main(String[]a){for(String x:a)System.out.println(CollectionExtDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-collection-ext-') as t:
 d=pathlib.Path(t);(d/'CollectionExtDemo.java').write_text(src);(d/'CDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CollectionExtDemo.java'),str(d/'CDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CollectionExtDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(200));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'CDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 200 operaciones List.of, addAll/sort, TreeMap/LinkedHashMap, vistas y fail-fast')
