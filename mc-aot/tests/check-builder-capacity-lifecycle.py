#!/usr/bin/env python3
"""Capacidad y longitud de StringBuilder frente a Java, incluso UTF-16."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class BuilderLifeProbe{public static int run(int n){try{StringBuilder b=n%3==0?new StringBuilder():n%3==1?new StringBuilder(n%30):new StringBuilder("abc");int v=b.capacity();b.append("abcdefghijklmnop😀");v=v*31+b.capacity();b.setLength(n%53);v=v*31+b.capacity();v=v*31+b.length();if((n&1)!=0)b.trimToSize();v=v*31+b.capacity();b.append("xxx");v=v*31+b.capacity();return v*31+b.toString().hashCode();}catch(StringIndexOutOfBoundsException e){return e.getMessage().hashCode();}}public static int wide(int n){StringBuilder source=new StringBuilder("😀");source.setLength(0);source.append("abc");StringBuilder b=new StringBuilder(n%7);b.append((CharSequence)source);return b.capacity()*31+b.toString().hashCode();}}'''
driver='''import net.minecraft.test.BuilderLifeProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("wide")?BuilderLifeProbe.wide(n):BuilderLifeProbe.run(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-builder-life-') as t:
 d=pathlib.Path(t);(d/'BuilderLifeProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'BuilderLifeProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/BuilderLifeProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(300));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver','run',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:
  a=j.splitlines();b=n.splitlines();i=next(i for i,(x,y) in enumerate(zip(a,b)) if x!=y);raise AssertionError((seq[i],a[i],b[i]))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/BuilderLifeProbe',str(d/'wide'),'wide','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(70));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver','wide',*map(str,vals)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'wide'),*[v for x in vals for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError(('wide coder retention',j,n))
 print(f'OK: {len(seq)+len(vals)} resultados capacidad/growth/setLength/trimToSize/coder UTF-16 frente a Java')
