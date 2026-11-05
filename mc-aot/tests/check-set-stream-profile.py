#!/usr/bin/env python3
"""Set.stream para conjuntos monohilo modelados, solo construcción y estado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.concurrent.*;import java.util.stream.*;
public class SetStreamProbe{static int calls;static boolean pred(String s){calls++;return true;}public static int run(int n){calls=0;Set<String> set=n%3==0?new HashSet<>():n%3==1?new LinkedHashSet<>():ConcurrentHashMap.newKeySet();set.add("x");Stream<String> a=set.stream();set.add("y");Stream<String> b=a.filter(SetStreamProbe::pred);if((n&1)!=0)try{a.filter(SetStreamProbe::pred);return -1;}catch(IllegalStateException e){}if((n&2)!=0)b.close();return calls+set.size()+(b.isParallel()?100:10);}public static int collect(int n){Set<String> s=new HashSet<>();s.add("x");return s.stream().collect(Collectors.joining(",","","")).length();}public static int max(int n){Set<String> s=new HashSet<>();s.add("x");return s.stream().max(Comparator.comparing(x->x.length())).isPresent()?1:0;}}
'''
driver='''import net.minecraft.test.SetStreamProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(SetStreamProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-set-stream-') as t:
 d=pathlib.Path(t);(d/'SetStreamProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SetStreamProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SetStreamProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 for method,want in [('collect','Stream.collect: solo ArrayList'),('max','Stream.max: solo fuente ArrayList')]:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SetStreamProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
  n=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if n.returncode==0 or want not in n.stderr:raise AssertionError((method,n.stderr))
 print(f'OK: {len(seq)} resultados Set.stream de HashSet/LinkedHashSet/KeySet, laziness y estado; collect/max sobre Set abortan')
