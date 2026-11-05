#!/usr/bin/env python3
"""ByteArrayInputStream de byte[] vivo: lectura, alias, mark/reset, cierre y EOF."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.io.*;public class ByteStreamProbe{public static int run(int n){byte[] a={0,1,-1,42,5};ByteArrayInputStream b=new ByteArrayInputStream(a);int result=b.read()*13+b.available();b.mark(1);a[1]=(byte)n;result=result*31+b.read();result=result*31+(int)b.skip(n%8-2);b.reset();result=result*31+b.read();result=result*31+(b.markSupported()?1:0);try{b.close();}catch(IOException e){return -2;}int k=b.read(a,2,3);result=result*31+k;result=result*31+a[2];result=result*31+a[3];result=result*31+a[4];result=result*31+b.read(a,0,0);return result;}
 public static int nullBuffer(int n){try{new ByteArrayInputStream(null);return 1;}catch(NullPointerException e){return 2;}}
 public static int badRange(int n){ByteArrayInputStream b=new ByteArrayInputStream(new byte[0]);try{b.read(new byte[2],n%7-3,2);return 1;}catch(IndexOutOfBoundsException e){return e.getMessage().hashCode();}}
}'''
driver='''import net.minecraft.test.ByteStreamProbe;public class Driver{public static void main(String[]a){for(String n:a){int x=Integer.parseInt(n);System.out.println(ByteStreamProbe.run(x));System.out.println(ByteStreamProbe.nullBuffer(x));System.out.println(ByteStreamProbe.badRange(x));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-byte-stream-') as t:
 d=pathlib.Path(t);(d/'ByteStreamProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ByteStreamProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 names=('run','nullBuffer','badRange')
 for m in names:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ByteStreamProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((m,p.stderr))
 seq=list(range(81));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout.splitlines();outs=[subprocess.run([str(d/m),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines() for m in names];n=[v for pair in zip(*outs) for v in pair]
 if j!=n:raise AssertionError([(i,a,b) for i,(a,b) in enumerate(zip(j,n)) if a!=b][:20])
 print(f'OK: {len(j)} resultados ByteArrayInputStream frente a Java 25, byte[] mutable y alias')
