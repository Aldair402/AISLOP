#!/usr/bin/env python3
"""Campos de arrays JDK vacíos reales: identidad y longitud, sin fingir soporte no vacío."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
final class FinalItem {static int initialized=7;}
class ArraysFields {
 static final StackTraceElement[] TRACE=new StackTraceElement[0];
 static final java.nio.ByteBuffer[] BUFFERS=new java.nio.ByteBuffer[0];
 static final java.security.cert.Certificate[] CERTS=new java.security.cert.Certificate[0];
 static final Throwable[] ERRORS=new Throwable[0];
 static final FinalItem[] ITEMS=new FinalItem[0];
}
public class EmptyArrayDemo {
 public static int run(int n){switch(n%6){case 0:return ArraysFields.TRACE.length;case 1:return ArraysFields.TRACE==ArraysFields.TRACE?1:0;case 2:return ArraysFields.BUFFERS.length+ArraysFields.CERTS.length;case 3:return ((Object[])ArraysFields.ERRORS).length;case 4:return ArraysFields.ITEMS.length;default:try {return ArraysFields.TRACE[0]==null?5:6;}catch(ArrayIndexOutOfBoundsException e){return 7;}}}
 public static int unsupported(int n){return new StackTraceElement[n].length;}
}'''
driver='''import net.minecraft.test.EmptyArrayDemo;public class EmptyDriver{public static void main(String[]a){for(String s:a)System.out.println(EmptyArrayDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-empty-array-') as t:
 d=pathlib.Path(t);(d/'EmptyArrayDemo.java').write_text(source);(d/'EmptyDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EmptyArrayDemo.java'),str(d/'EmptyDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EmptyArrayDemo']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I','unsupported','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(120));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'EmptyDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
 a=subprocess.run([str(d/'native'),*[x for n in vals for x in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 p=subprocess.run([str(d/'native'),'1','1'],capture_output=True,text=True)
 if p.returncode==0 or 'solo longitud cero' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 120 operaciones de arrays JDK vacíos; longitud positiva aborta explícitamente')
