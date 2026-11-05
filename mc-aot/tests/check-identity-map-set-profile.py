#!/usr/bin/env python3
"""Diferencial Java 25 de mapa por identidad y vista viva newSetFromMap."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.*;
public class IdentityProfile {
 static class Key { }
 public static int run(int n) {
  IdentityHashMap<Object,Boolean> map=new IdentityHashMap<>();
  Set<Object> set=Collections.newSetFromMap(map);
  String a=new StringBuilder().append("igual").toString();
  String b=new StringBuilder().append("igual").toString();
  Key k=new Key(); Key k2=new Key(); int v=0;
  if(set.add(a))v|=1; if(set.add(b))v|=2; if(!set.add(a))v|=4;
  if(map.size()==2 && set.contains(a) && set.contains(b))v|=8;
  if(set.add(null) && !set.add(null))v|=16;
  if(set.add(k) && !set.contains(k2))v|=32;
  if(map.put(k2,null)==null && map.containsKey(k2) && set.contains(k2))v|=64;
  if(set.add(k2) && map.get(k2)==Boolean.TRUE) v|=128;
  map.put(k2,null); if(!set.remove(k2) && !map.containsKey(k2)) v|=256;
  map.put(k2,Boolean.FALSE); if(set.remove(k2) && !map.containsKey(k2))v|=512;
  Set<Object> second=Collections.newSetFromMap(new IdentityHashMap<Object,Boolean>());
  if(second.addAll(set) && second.size()==set.size() && !second.addAll(set))v|=1024;
  if(second.addAll(second)==false && second.contains(k))v|=2048;
  if(map.remove(a)==Boolean.TRUE && !set.contains(a) && set.contains(b))v|=4096;
  map.clear(); if(set.isEmpty())v|=8192;
  if((n&1)!=0){second.clear();if(second.isEmpty())v|=16384;}
  try {newBad();}catch(IllegalArgumentException expected){v|=32768;}
  try {nullMap();}catch(NullPointerException expected){v|=65536;}
  return v;
 }
 static void newBad(){IdentityHashMap<Object,Boolean> m=new IdentityHashMap<>();m.put(null,Boolean.TRUE);Collections.newSetFromMap(m);}
 static void nullMap(){Collections.newSetFromMap(null);}
 public static int unsupported(int n){Set<Object>s=Collections.newSetFromMap(new IdentityHashMap<Object,Boolean>());s.add("x");return s.iterator().hasNext()?1:0;}
 public static int wrongMap(int n){Set<Object>s=Collections.newSetFromMap(new HashMap<Object,Boolean>());return s.size();}
}
'''
driver='''import net.minecraft.test.IdentityProfile;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(IdentityProfile.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-identity-profile-') as t:
 d=pathlib.Path(t);(d/'IdentityProfile.java').write_text(source);(d/'Driver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'IdentityProfile.java'),str(d/'Driver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/IdentityProfile',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 for name in ('run','unsupported','wrongMap'):compile(name)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 for name,msg in [('unsupported','iterator de colección no soportada'),('wrongMap','newSetFromMap: solo IdentityHashMap soportado')]:
  p=subprocess.run([str(d/name),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or msg not in p.stderr:raise AssertionError((name,p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Java/IdentityHashMap y vista viva, identidad/null/alias/addAll; dos guardas')
