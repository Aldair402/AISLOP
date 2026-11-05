#!/usr/bin/env python3
"""Comparator.comparing con Function lambda y claves Integer; límites explícitos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.Comparator;import java.util.function.Function;
public class ComparatorDemo{static int calls;static final class Other implements Function<Integer,Integer>{public Integer apply(Integer x){return x;}}
 public static int run(int n){try{if(n==0)return 7;Function<Integer,Integer> f=n==1?null: x->{calls++;return x;};Comparator<Integer> c=Comparator.comparing(f);if(n==2)return calls+1;Integer a=(n&1)==0?Integer.valueOf(n):null;Integer b=n%5==0?null:(n&2)==0?Integer.valueOf(0):Integer.valueOf(100);int value=c.compare(a,b);return calls*10+value+1;}catch(NullPointerException e){return 100+calls;}}
 public static int exception(int n){calls=0;try{Function<Integer,Integer> f=x->{calls++;if(x==null)throw new IllegalArgumentException();return x;};Comparator<Integer> c=Comparator.comparing(f);c.compare((n&1)==0?null:1,(n&2)==0?null:2);return 200+calls;}catch(IllegalArgumentException e){return 100+calls;}}
 public static int unsupported(int n){return Comparator.comparing(new Other()).compare(1,2);}
 public static int key(int n){Comparator<String> c=Comparator.comparing(x->x);return c.compare("a","b");}
}'''
driver='''import net.minecraft.test.ComparatorDemo;public class Driver{public static void main(String[]a){for(String s:a)System.out.println(s.startsWith("e")?ComparatorDemo.exception(Integer.parseInt(s.substring(1))):ComparatorDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-comparator-') as t:
 d=pathlib.Path(t);(d/'ComparatorDemo.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ComparatorDemo.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ComparatorDemo',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-30,31))+[-2147483648,2147483647];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('exception');nums=list(range(32));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*[f'e{n}' for n in nums]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'exception'),*[v for n in nums for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError(('exceptions',java,native))
 for method,want in [('unsupported','Function fuera del perfil'),('key','claves distintas de Integer')]:
  compile(method);p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or want not in p.stderr:raise AssertionError((method,p.returncode,p.stdout,p.stderr))
 print(f'OK: {len(seq)+len(nums)} resultados Comparator.comparing/compare, null, orden y efectos de extractor; Function concreta y otras claves abortan')
