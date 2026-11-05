#!/usr/bin/env python3
"""StackWalker.RETAIN_CLASS_REFERENCE en cadenas directas traducidas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;class CallerA {static Class<?> ask(){return CallerB.ask();}static Class<?> recursive(int n){return n==0?CallerB.ask():recursive(n-1);}}class CallerB {static final StackWalker w=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE);static Class<?> ask(){return w.getCallerClass();}}
public class StackWalkerDemo {static Class<?> a(){return CallerA.ask();}public static int run(int n){try{switch(n){case 0:return CallerA.ask().getName().equals("net.minecraft.test.CallerA")?1:0;case 1:return CallerB.ask().getName().equals("net.minecraft.test.StackWalkerDemo")?2:0;case 2:return CallerA.recursive(10).getName().equals("net.minecraft.test.CallerA")?3:0;case 3:return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE)==StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE)?0:4;case 4:StackWalker.Option o=null;StackWalker.getInstance(o);return 0;case 5:StackWalker w=null;w.getCallerClass();return 0;case 6:return StackWalker.getInstance()==StackWalker.getInstance()?6:0;case 7:StackWalker.getInstance().getCallerClass();return 0;case 8:return StackWalker.getInstance()!=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE)?8:0;default:return 99;}}catch(NullPointerException e){return 105;}catch(UnsupportedOperationException e){return 107;}}}
'''
driver='''import net.minecraft.test.StackWalkerDemo;public class WalkerDriver{public static void main(String[]a){for(String s:a)System.out.println(StackWalkerDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-walker-') as t:
 d=pathlib.Path(t);(d/'StackWalkerDemo.java').write_text(source);(d/'WalkerDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StackWalkerDemo.java'),str(d/'WalkerDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/StackWalkerDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=[str(n) for n in range(9)]*20;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'WalkerDriver',*seq],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} resultados Java StackWalker: llamantes, recursión, inicialización, identidad, opciones y null')
