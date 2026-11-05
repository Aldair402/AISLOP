#!/usr/bin/env python3
"""Vista viva de Properties.entrySet e iteración solo sobre mapa vacío."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;
public class EntryProbe{public static int run(int n){Properties p=new Properties();Set<Map.Entry<Object,Object>> a=p.entrySet(),b=p.entrySet();int r=(a==b?1:0)+(a.size()==0?2:0);Iterator<Map.Entry<Object,Object>> i=a.iterator();if(i.hasNext())return -1;try{i.next();return -2;}catch(NoSuchElementException e){}if((n&1)!=0){p.setProperty("key","value");r+=a.size()*4;}try{Properties z=null;z.entrySet();return -3;}catch(NullPointerException e){}return r;}
 public static int nonempty(int n){Properties p=new Properties();p.setProperty("a","b");return p.entrySet().iterator().hasNext()?1:0;}
 public static int modified(int n){Properties p=new Properties();Iterator<?> it=p.entrySet().iterator();p.setProperty("a","b");return it.hasNext()?1:0;}}
'''
driver='''import net.minecraft.test.EntryProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(EntryProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-properties-entryset-') as t:
 d=pathlib.Path(t);(d/'EntryProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EntryProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EntryProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 for method in ['nonempty','modified']:
  compile(method);p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or 'iteración no vacía o modificada no soportada' not in p.stderr:raise AssertionError((method,p.returncode,p.stderr))
 print(f'OK: {len(seq)} resultados Java entrySet, vistas vivas e iteración vacía; entradas no vacías/modificadas abortan')
