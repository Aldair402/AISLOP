#!/usr/bin/env python3
"""collect(joining) secuencial para ArrayList de String/null, sin map/sorted."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.stream.*;
public class JoinProbe{public static int run(int n){try{ArrayList<String> xs=new ArrayList<>();Stream<String> s=xs.stream();if((n&1)!=0)xs.add("uno");if((n&2)!=0)xs.add(null);if((n&4)!=0)xs.add("🧱é");String d=(n&8)!=0?null:"|",p=(n&16)!=0?null:"<",q=(n&32)!=0?null:">";Collector<CharSequence,?,String> c=Collectors.joining(d,p,q);String v=s.collect(c);try{s.collect(c);return -2;}catch(IllegalStateException e){}return v.hashCode();}catch(NullPointerException e){String msg=e.getMessage();return msg==null?7:msg.equals("The prefix must not be null")?8:msg.equals("The delimiter must not be null")?9:msg.equals("The suffix must not be null")?10:11;}}
 public static int closed(int n){ArrayList<String> a=new ArrayList<>();Stream<String> s=a.stream();s.close();try{s.collect(null);return -1;}catch(NullPointerException e){}try{s.collect(Collectors.joining(",","[","]"));return -2;}catch(IllegalStateException e){return 5;}}
 public static int mapped(int n){ArrayList<String>a=new ArrayList<>();return a.stream().map(x->x).collect(Collectors.joining(",","[","]")).length();}
}'''
driver='''import net.minecraft.test.JoinProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(JoinProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-stream-joining-') as t:
 d=pathlib.Path(t);(d/'JoinProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'JoinProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/JoinProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-80,81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('closed');p=subprocess.run([str(d/'closed'),'0','0'],capture_output=True,text=True,check=True)
 if p.stdout!='5\n':raise AssertionError((p.stdout,p.stderr))
 compile('mapped');p=subprocess.run([str(d/'mapped'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Stream.collect: solo ArrayList directo sin etapas' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)+1} resultados Java collect(joining) con Unicode/null/estado; map aborta explícitamente')
