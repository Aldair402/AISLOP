#!/usr/bin/env python3
"""max secuencial de ArrayList, comparador de claves Integer y mutación rechazada."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.stream.*;
public class MaxProbe {static final class Item {final Integer value;Item(int n){value=n;}Integer key(){calls++;return value;}}static int calls;static Integer key(Integer x){calls++;return x;}
 public static int run(int n){calls=0;try{Collection<Integer> xs=new ArrayList<>();Stream<Integer> s=xs.stream();Comparator<Integer> c=Comparator.comparing(MaxProbe::key);if(n%7==0){}else if(n%7==1)xs.add(null);else{xs.add(n);xs.add(-5);xs.add(10);xs.add(n);}
 if((n&8)!=0){try{s.max(null);return -1;}catch(NullPointerException e){}}
 if((n&16)!=0){s.close();try{s.max(null);return -2;}catch(NullPointerException e){}try{s.max(c);return -3;}catch(IllegalStateException e){return 300+calls;}}
 Optional<Integer> m=s.max(c);int value=m.orElse(-99);try{s.max(c);return -4;}catch(IllegalStateException e){}return value+1000+calls*10;}catch(NullPointerException e){return 200+calls;}}
 public static int objects(int n){calls=0;ArrayList<Item> xs=new ArrayList<>();Item a=new Item(200),b=new Item((n&1)==0?200:201);xs.add(a);xs.add(b);Item best=xs.stream().max(Comparator.comparing(Item::key)).orElse(null);return (best==a?1:2)+calls*10;}
 public static int mutate(int n){ArrayList<Integer> xs=new ArrayList<>();xs.add(2);xs.add(3);Comparator<Integer> c=Comparator.comparing(x->{xs.add(1);return x;});return xs.stream().max(c).orElse(0);}
}'''
driver='''import net.minecraft.test.MaxProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(n.startsWith("o")?MaxProbe.objects(Integer.parseInt(n.substring(1))):MaxProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-stream-max-') as t:
 d=pathlib.Path(t);(d/'MaxProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MaxProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MaxProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-80,81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('objects');nums=list(range(41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*[f'o{n}' for n in nums]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'objects'),*[v for n in nums for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError(('objects',java,native))
 compile('mutate');p=subprocess.run([str(d/'mutate'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'modificación estructural durante recorrido no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stdout,p.stderr))
 print(f'OK: {len(seq)+len(nums)} resultados Java de ArrayList.stream().max, orden, late-binding, vacío/null y cierre; mutación durante recorrido aborta')
