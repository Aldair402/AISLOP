#!/usr/bin/env python3
"""System.out/err distintos, alias e impresiones admitidas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.io.PrintStream;
public class StreamsDemo {
 static PrintStream saved=System.err;
 public static int run(int n){PrintStream x=n<4?System.out:System.err;switch(n%4){case 0:x.println("hola🦀");break;case 1:x.println((String)null);break;case 2:x.println(-42);break;default:x.println(true);}
 return (saved==System.err?1:0)+(saved!=System.out?2:0)+(x==saved?4:0);}
}'''
driver='''import net.minecraft.test.StreamsDemo;public class StreamsDriver{public static void main(String[] a){for(String s:a)System.out.println(StreamsDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-streams-') as t:
 d=pathlib.Path(t);(d/'StreamsDemo.java').write_text(source);(d/'StreamsDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StreamsDemo.java'),str(d/'StreamsDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/StreamsDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in range(8)];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'StreamsDriver',*vals],capture_output=True,check=True);native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,check=True)
 if (java.stdout,java.stderr)!=(native.stdout,native.stderr):raise AssertionError((java.stdout,native.stdout,java.stderr,native.stderr))
 print('OK: ocho impresiones stdout/stderr, null, UTF-8, enteros, booleanos e identidad de streams coinciden byte a byte')
