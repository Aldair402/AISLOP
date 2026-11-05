#!/usr/bin/env python3
"""Pipelines perezosos map/dropWhile/findFirst en prefijos traducidos de StackWalker."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.*;import java.util.stream.*;
final class DropA{static Class<?> go(int n){return DropB.go(n);}}
final class DropB{static Class<?> go(int n){Class<?> target=(n&1)==0?DropB.class:DropA.class;return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->s.map(StackWalker.StackFrame::getDeclaringClass).map(c->{DropProbe.maps++;return c;}).dropWhile(c->{DropProbe.first++;return c!=target;}).dropWhile(c->{DropProbe.second++;return (n&2)!=0&&DropProbe.second==1;}).findFirst().orElse(null));}}
public class DropProbe{static int maps,first,second;public static int run(int n){maps=first=second=0;Class<?> c=DropA.go(n);int result=c==DropB.class?1:c==DropA.class?2:c==DropProbe.class?3:99;return result+maps*10+first*100+second*1000;}
 public static int errors(int n){try{return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->{Stream<Class<?>> a=s.map(StackWalker.StackFrame::getDeclaringClass);if(n%4==0){try{s.map(StackWalker.StackFrame::getDeclaringClass);return -1;}catch(IllegalStateException e){return 11;}}if(n%4==1){try{a.dropWhile(null);return -2;}catch(NullPointerException e){return 12;}}if(n%4==2)return a.dropWhile(c->{throw new IllegalArgumentException();}).findFirst().isPresent()?1:2;return a.map(c->(Class<?>)null).findFirst().isPresent()?3:4;});}catch(IllegalArgumentException e){return 13;}catch(NullPointerException e){return 14;}}
 public static int detached(int n){Stream<Class<?>> s=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(x->x.map(StackWalker.StackFrame::getDeclaringClass).dropWhile(c->false));return s.findFirst().isPresent()?1:0;}
 public static int external(int n){return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->s.map(StackWalker.StackFrame::getDeclaringClass).dropWhile(c->true).findFirst().isPresent()?1:0);}
 public static int callback(int n){return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->s.map(StackWalker.StackFrame::getDeclaringClass).dropWhile(c->StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).getCallerClass()==DropProbe.class).findFirst().isPresent()?1:0);}
}'''
driver='''import net.minecraft.test.DropProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("run")?DropProbe.run(n):DropProbe.errors(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-walk-dropwhile-') as t:
 d=pathlib.Path(t);(d/'DropProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DropProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DropProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 seq=list(range(80))
 for method in ['run','errors']:
  compile(method);j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',method,*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/method),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
  if j!=n:raise AssertionError((method,j,n))
 for method,reason in [('detached','consumo fuera de walk no modelado'),('external','frames externos no modelados'),('callback','frame JDK no modelado')]:
  compile(method);p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or reason not in p.stderr:raise AssertionError((method,p.returncode,p.stderr))
 print(f'OK: {len(seq)*2} resultados Java map/dropWhile/findFirst, short-circuit, estado/null/excepciones y guardas')
