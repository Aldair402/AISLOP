#!/usr/bin/env python3
"""Perfil AbstractSpliterator usado por ServiceLoaderUtil; no streams ni trySplit."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.*;import java.util.function.Consumer;
public class SplitProbe {
 public static int run(int n){long estimate=(long)n*1000000L;int flags=(n&1)!=0?64:0;flags|=(n&2)!=0?16:0;Spliterator<Object> s=new Split(estimate,flags);
  int score=s.characteristics();if(s.hasCharacteristics(64))score+=100;if(s.hasCharacteristics(16448))score+=200;
  long exact=s.getExactSizeIfKnown();return score+(int)s.estimateSize()+(int)exact;}
 public static int bad(int n){Spliterator<Object> s=new Evil(n);return s.characteristics();}
 public static int split(int n){Spliterator<Object> s=new Split(n,0);return s.trySplit()==null?0:1;}
}
final class Split extends Spliterators.AbstractSpliterator<Object>{Split(long size,int flags){super(size,flags);}public boolean tryAdvance(Consumer<? super Object> c){return false;}}
final class Evil extends Spliterators.AbstractSpliterator<Object>{Evil(long size){super(size,0);}public boolean tryAdvance(Consumer<? super Object> c){return false;}public int characteristics(){return 123;}}
'''
driver='''import net.minecraft.test.SplitProbe;public class SplitDriver{public static void main(String[]a){for(String n:a)System.out.println(SplitProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-spliterator-') as temp:
 d=pathlib.Path(temp);(d/'SplitProbe.java').write_text(source);(d/'SplitDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SplitProbe.java'),str(d/'SplitDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SplitProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-50,51))+[-2147483648,2147483647];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SplitDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'run'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or native.stdout!=java.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('bad')
 if p.returncode==0 or 'AbstractSpliterator: subclase u override no soportado' not in p.stderr:raise AssertionError(('override',p.returncode,p.stderr))
 p=compile('split')
 if p.returncode==0 or 'invokeinterface no soportado: java/util/Spliterator.trySplit' not in p.stderr:raise AssertionError(('trySplit',p.returncode,p.stderr))
 print(f'OK: {len(vals)} resultados de AbstractSpliterator estimateSize/characteristics/getExactSizeIfKnown/hasCharacteristics, Java 25; guardas de override y trySplit')
