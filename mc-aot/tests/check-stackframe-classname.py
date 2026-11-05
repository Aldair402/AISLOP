#!/usr/bin/env python3
"""StackFrame.getClassName para prefijos traducidos, con y sin retain."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;class FrameNameA{static String go(boolean keep){StackWalker w=keep?StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE):StackWalker.getInstance();return w.walk(s->{StackWalker.StackFrame f=s.findFirst().get();String a=f.getClassName(),b=f.getClassName();return (a==b&&a.equals("net.minecraft.test.FrameNameA"))?a:"wrong";});}}public class FrameNameProbe{public static int run(int n){String s=FrameNameA.go((n&1)!=0);return s.equals("net.minecraft.test.FrameNameA")?1:2;}public static int nul(int n){try{StackWalker.StackFrame f=null;return f.getClassName().length();}catch(NullPointerException e){return 5;}}}'''
driver='''import net.minecraft.test.FrameNameProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(FrameNameProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-stackframe-name-') as t:
 d=pathlib.Path(t);(d/'FrameNameProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FrameNameProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FrameNameProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('nul');p=subprocess.run([str(d/'nul'),'0','0'],capture_output=True,text=True,check=True)
 if p.stdout!='5\n':raise AssertionError(p.stdout)
 print(f'OK: {len(seq)+1} resultados StackFrame.getClassName, sin/con retain e identidad/null')
