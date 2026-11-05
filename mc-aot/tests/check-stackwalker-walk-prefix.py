#!/usr/bin/env python3
"""walk/skip/findFirst sobre prefijos de frames traducidos, sin fingir límite externo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.stream.*;import java.util.function.*;
final class WalkA {static Class<?> go(int n){return WalkB.go(n);}}
final class WalkB {static Class<?> go(int n){return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->s.skip(n).findFirst().map(StackWalker.StackFrame::getDeclaringClass).orElse(null));}}
public class WalkProbe {
 public static int run(int n){try{int k=n%4;Class<?> c=WalkA.go(k);return c==WalkB.class?1:c==WalkA.class?2:c==WalkProbe.class?3:99;}catch(IllegalArgumentException e){return e.getMessage().equals("-1")||e.getMessage().equals("-2")||e.getMessage().equals("-3")?4:5;}}
 public static int detached(int n){Stream<StackWalker.StackFrame> s=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(x->x);return s.findFirst().isPresent()?1:0;}
 public static int external(int n){return WalkA.go(50)==null?1:0;}
 public static int noRetain(int n){try{StackWalker.getInstance().walk(s->s.findFirst().get().getDeclaringClass());return 0;}catch(UnsupportedOperationException e){return 7;}}
 public static int callbackCaller(int n){return Optional.of("x").map(x->StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).getCallerClass()).get()==WalkProbe.class?1:0;}
 public static int callbackWalk(int n){return Optional.of("x").map(x->StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->s.skip(1).findFirst().get().getDeclaringClass())).get()==WalkProbe.class?1:0;}
 public static int nul(int n){try{StackWalker w=StackWalker.getInstance();w.walk(null);return 0;}catch(NullPointerException e){return 6;}}
}'''
driver='''import net.minecraft.test.WalkProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(n.startsWith("r")?WalkProbe.noRetain(0):n.startsWith("z")?WalkProbe.nul(0):WalkProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-walk-prefix-') as t:
 d=pathlib.Path(t);(d/'WalkProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'WalkProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/WalkProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=[n for n in range(-40,41) if n<0 or n%4!=3]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 for method,expected in [('noRetain','7\n'),('nul','6\n')]:
  compile(method);p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True,check=True)
  oracle=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver','r' if method=='noRetain' else 'z'],capture_output=True,text=True,check=True).stdout
  if p.stdout!=expected or p.stdout!=oracle:raise AssertionError((method,p.stdout,oracle,p.stderr))
 for method,reason in [('detached','consumo fuera de walk no modelado'),('external','frames externos no modelados'),('callbackCaller','frame JDK no modelado'),('callbackWalk','frame JDK no modelado')]:
  compile(method);p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or reason not in p.stderr:raise AssertionError((method,p.returncode,p.stderr))
 print(f'OK: {len(seq)+2} comparaciones Java walk/skip/findFirst/map, null, opciones y valores negativos; frames externos y consumo fuera de walk abortan')
