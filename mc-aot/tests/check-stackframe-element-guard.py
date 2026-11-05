#!/usr/bin/env python3
"""La referencia StackFrame::toStackTraceElement falla explícitamente al usarse."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.*;public class FrameElementProbe{public static int run(int n){Function<StackWalker.StackFrame,StackTraceElement> f=StackWalker.StackFrame::toStackTraceElement;if(n==0)return Optional.<StackWalker.StackFrame>empty().map(f).isPresent()?1:7;if(n==1)try{f.apply(null);return 0;}catch(NullPointerException e){return 8;}StackWalker.StackFrame x=StackWalker.getInstance().walk(s->s.findFirst().get());return f.apply(x)==null?1:2;}}'''
driver='''import net.minecraft.test.FrameElementProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(FrameElementProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-frame-element-') as t:
 d=pathlib.Path(t);(d/'FrameElementProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FrameElementProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FrameElementProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver','0','1'],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),'0','0','0','1'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'native'),'0','2'],capture_output=True,text=True)
 if p.returncode==0 or 'StackFrame.toStackTraceElement: método, línea y archivo no modelados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: referencia no invocada y null coinciden con Java; conversión de frame aborta explícitamente')
