#!/usr/bin/env python3
"""Collections.emptySet singleton, operaciones vacías y rechazos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class EmptySetProbe{public static int run(int n){Set<Object>s=Collections.emptySet();int v=(s==Collections.emptySet()?1:0)+(s.isEmpty()?2:0)+(s.size()==0?4:0)+(!s.contains(null)?8:0)+(!s.remove("x")?16:0)+(!s.iterator().hasNext()?32:0);s.clear();try{s.add("x");}catch(UnsupportedOperationException e){v+=64;}try{s.iterator().next();}catch(NoSuchElementException e){v+=128;}List<Object> l=new ArrayList<>();if((n&1)!=0)l.add("x");try{if(!s.addAll(l))v+=256;}catch(UnsupportedOperationException e){v+=512;}return v;}}'''
driver='''import net.minecraft.test.EmptySetProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(EmptySetProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-empty-set-') as t:
 d=pathlib.Path(t);(d/'EmptySetProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EmptySetProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EmptySetProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Collections.emptySet identidad/iterator/add/remove/addAll frente a Java')
