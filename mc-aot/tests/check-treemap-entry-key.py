#!/usr/bin/env python3
"""Map.Entry.getKey de TreeMap, orden/identidad y guardas por modificación."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class EntryKeyProbe{public static int run(int n){TreeMap<String,String> m=new TreeMap<>();String a="a",b="b";m.put(b,"B");m.put(a,"A");Iterator<Map.Entry<String,String>> it=m.entrySet().iterator();Map.Entry<String,String> x=it.next(),y=it.next();return (x.getKey()==a?1:0)+(y.getKey()==b?2:0)+(x.getValue().equals("A")?4:0);}public static int stale(int n){TreeMap<String,String> m=new TreeMap<>();m.put("a","A");Map.Entry<String,String> x=m.entrySet().iterator().next();m.put("b","B");return x.getKey().length();}}'''
driver='''import net.minecraft.test.EntryKeyProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(EntryKeyProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-treemap-key-') as t:
 d=pathlib.Path(t);(d/'EntryKeyProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EntryKeyProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EntryKeyProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('stale');p=subprocess.run([str(d/'stale'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Map.Entry tras modificación estructural no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Java TreeMap Entry.getKey y getValue; modificación estructural aborta')
