#!/usr/bin/env python3
"""Etapas sorted perezosas, sin implementar consumo ordenado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.stream.*;
public class SortedProbe {static int calls;static Integer key(Integer x){calls++;return x;}static boolean pred(Integer x){calls+=10;return true;}
 public static int run(int n){try{Collection<Integer> list=new ArrayList<>();list.add(3);Stream<Integer> a=list.stream();Comparator<Integer> c=Comparator.comparing(SortedProbe::key);if((n&1)!=0){try{a.sorted(null);return -1;}catch(NullPointerException e){}try{a.sorted(c);return -2;}catch(IllegalStateException e){return calls+10;}}Stream<Integer> b=a.sorted(c);if((n&2)!=0){try{a.sorted(null);return -3;}catch(IllegalStateException e){}}if((n&4)!=0)b=b.filter(SortedProbe::pred);if((n&8)!=0)b=b.sorted(c);if((n&16)!=0){b.close();try{b.sorted(null);return -4;}catch(IllegalStateException e){}}return calls+(b.isParallel()?100:20);}catch(Exception e){return -5;}}
 public static int nil(int n){try{Stream<Integer> x=null;x.sorted(null);return 0;}catch(NullPointerException e){return 1;}}
}'''
driver='''import net.minecraft.test.SortedProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(SortedProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-sorted-') as t:
 d=pathlib.Path(t);(d/'SortedProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SortedProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SortedProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('nil');p=subprocess.run([str(d/'nil'),'0','0'],capture_output=True,text=True,check=True)
 if p.stdout!='1\n':raise AssertionError((p.stdout,p.stderr))
 print(f'OK: {len(seq)+1} resultados sorted perezoso, null, cierre y orden de validaciones; consumo ordenado no implementado')
