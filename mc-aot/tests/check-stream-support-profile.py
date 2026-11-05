#!/usr/bin/env python3
"""Construcción perezosa secuencial StreamSupport con spliterator restringido."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.Consumer;import java.util.stream.*;
public class StreamProbe {
 static final class OtherPredicate implements java.util.function.Predicate<Object>{public boolean test(Object x){return true;}}
 static int advances;public static void advanced(){advances++;}public static boolean accepted(Object x){advances+=100;return true;}
 public static int run(int n){int flags=(n&1)!=0?64:0;if((n&2)!=0)flags|=4;Spliterator<Object> s=(n==7)?null:new Split(n,flags);
  try{Stream<Object> stream=StreamSupport.stream(s,false);int result=advances+(stream.isParallel()?100:10);stream.close();stream.close();return result+(stream.isParallel()?1000:0);}
  catch(IllegalStateException e){return 200+advances;}catch(NullPointerException e){return 300+advances;}}
 public static int filter(int n){try{Stream<Object> a=StreamSupport.stream(new Split(5,0),false);Collection<Object> seen=new HashSet<>();Stream<Object> b=a.filter(x->seen.add(x.getClass()));if((n&1)!=0){try{a.filter(StreamProbe::accepted);return -1;}catch(IllegalStateException e){}}if((n&2)!=0){try{b.filter(null);return -2;}catch(NullPointerException e){}try{a.filter(null);return -4;}catch(NullPointerException e){}}if((n&8)!=0){try{Stream<Object> z=null;z.filter(new OtherPredicate());return -5;}catch(NullPointerException e){}}Stream<Object> c=b.filter(StreamProbe::accepted);c.close();if((n&4)!=0){try{c.filter(StreamProbe::accepted);return -3;}catch(IllegalStateException e){}}return advances+seen.size()+(c.isParallel()?1000:50);}catch(Exception e){return -10;}}
 public static int concrete(int n){return StreamSupport.stream(new Split(0,0),false).filter(new OtherPredicate()).isParallel()?1:0;}
 public static int parallel(int n){Stream<Object> stream=StreamSupport.stream(new Split(n,0),true);return stream.isParallel()?1:0;}
}
final class Split extends Spliterators.AbstractSpliterator<Object>{Split(long size,int flags){super(size,flags);}public boolean tryAdvance(Consumer<? super Object> c){StreamProbe.advanced();return false;}}
'''
driver='''import net.minecraft.test.StreamProbe;public class StreamDriver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("filter")?StreamProbe.filter(n):StreamProbe.run(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-stream-support-') as temp:
 d=pathlib.Path(temp);(d/'StreamProbe.java').write_text(source);(d/'StreamDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StreamProbe.java'),str(d/'StreamDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/StreamProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-20,21))+[-2147483648,2147483647];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'StreamDriver','run',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'run'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or native.stdout!=java.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('filter')
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'StreamDriver','filter',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'filter'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or native.stdout!=java.stdout:raise AssertionError(('filter',java.stdout,native.stdout,native.stderr))
 p=compile('concrete')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'concrete'),'0','0'],capture_output=True,text=True,timeout=30)
 if native.returncode==0 or 'Stream.filter: Predicate fuera del perfil' not in native.stderr:raise AssertionError(('concrete predicate guard',native.returncode,native.stderr))
 p=compile('parallel')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'parallel'),'0','1'],capture_output=True,text=True,timeout=10)
 if native.returncode==0 or 'stream paralelo no soportado' not in native.stderr:raise AssertionError(('paralelo',native.returncode,native.stderr))
 print(f'OK: {len(vals)*2} resultados StreamSupport/filter secuencial, laziness, cierre, null/SORTED y guardias paralelo/predicado no lambda; sin operaciones terminales')
