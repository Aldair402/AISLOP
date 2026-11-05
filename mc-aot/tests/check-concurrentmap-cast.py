#!/usr/bin/env python3
"""Cast/instanceof ConcurrentMap para ConcurrentHashMap y objetos JDK conocidos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.concurrent.*;
public class CastProbe{static final class Other{}public static int unverified(int n){Object o=new Other();return o instanceof ConcurrentMap?1:0;}public static int run(int n){try{Object o=n%3==0?null:n%3==1?new ConcurrentHashMap<>():new HashMap<>();boolean b=o instanceof ConcurrentMap;ConcurrentMap<?,?> x=(ConcurrentMap<?,?>)o;return (b?1:0)+(x==o?2:0);}catch(ClassCastException e){return 9;}}}
'''
driver='''import net.minecraft.test.CastProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(CastProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-concurrentmap-cast-') as t:
 d=pathlib.Path(t);(d/'CastProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CastProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CastProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CastProbe',str(d/'guard'),'unverified','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'guard'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'objeto proyecto no verificado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados cast/instanceof ConcurrentMap, identidad, HashMap y null; objetos proyecto no verificados abortan')
