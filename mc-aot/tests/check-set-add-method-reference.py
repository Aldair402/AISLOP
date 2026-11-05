#!/usr/bin/env python3
"""Referencia de método Set::add, Consumer descarta resultado; Predicate lo conserva."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.*;import java.util.concurrent.*;public class SetMethodProbe {
 public static int run(int n){try{Set<String> s=(n&1)==0?new LinkedHashSet<>():ConcurrentHashMap.newKeySet();Consumer<String> c=s::add;Predicate<String> p=s::add;c.accept("a");c.accept("a");int r=p.test("b")?1:0;r+=p.test("a")?2:0;r+=s.size()*10;if((n&2)!=0){try{c.accept(null);r+=100;}catch(NullPointerException e){r+=200;}}return r;}catch(Exception e){return -1;}}
 public static int nullBound(int n){try{Set<String>s=null;Consumer<String> c=s::add;return 0;}catch(NullPointerException e){return 7;}}
}'''
driver='''import net.minecraft.test.SetMethodProbe;public class SetMethodDriver{public static void main(String[]a){for(String n:a)System.out.println(SetMethodProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-set-method-') as tmp:
 d=pathlib.Path(tmp);(d/'SetMethodProbe.java').write_text(source);(d/'SetMethodDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SetMethodProbe.java'),str(d/'SetMethodDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SetMethodProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SetMethodDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('nullBound')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
 if native.returncode or native.stdout!='7\n':raise AssertionError(('bound null',native.stdout,native.stderr))
 print(f'OK: {len(vals)+1} resultados Set::add como Consumer/Predicate, captura, duplicados y null frente a Java')
