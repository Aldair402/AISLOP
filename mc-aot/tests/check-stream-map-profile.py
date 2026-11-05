#!/usr/bin/env python3
"""Etapa map perezosa y estado; el consumo transformado no se simula."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.stream.*;
public class MapProbe {static int calls;static Integer transform(Integer x){calls++;return x+1;}static boolean yes(Integer x){calls+=10;return true;}
 public static int run(int n){try{ArrayList<Integer> xs=new ArrayList<>();xs.add(2);Stream<Integer> a=xs.stream();if((n&1)!=0){try{a.map(null);return -1;}catch(NullPointerException e){}}Stream<Integer> b=a.map(MapProbe::transform);if((n&2)!=0){try{a.map(null);return -2;}catch(NullPointerException e){}try{a.map(MapProbe::transform);return -3;}catch(IllegalStateException e){}}if((n&4)!=0)b=b.filter(MapProbe::yes);if((n&8)!=0)b=b.sorted(Comparator.comparing(x->x));if((n&16)!=0){b.close();try{b.map(null);return -4;}catch(NullPointerException e){}try{b.map(MapProbe::transform);return -5;}catch(IllegalStateException e){}}return calls+(b.isParallel()?100:20);}catch(Exception e){return -6;}}
}'''
driver='''import net.minecraft.test.MapProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(MapProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-stream-map-') as t:
 d=pathlib.Path(t);(d/'MapProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MapProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MapProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} resultados map perezoso, encadenado, null, cierre y estado; consumo transformado no implementado')
