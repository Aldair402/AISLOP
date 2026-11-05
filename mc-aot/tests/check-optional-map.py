#!/usr/bin/env python3
"""Optional.map con lambdas, evaluación diferida, excepciones y cast Optional."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.*;public class OptionalMapProbe{static int calls;public static int run(int n){calls=0;try{Optional<String> a=(n&1)==0?Optional.of("abc"):Optional.empty();Function<String,String> f=(n&2)!=0?null:x->{calls++;if((n&4)!=0)throw new IllegalArgumentException();return (n&8)!=0?null:x;};Optional<String> b=a.map(f);return calls*10+(b.isPresent()?1:2);}catch(NullPointerException e){return 30+calls;}catch(IllegalArgumentException e){return 40+calls;}}
 public static int cast(int n){try{Object x=n%3==0?null:n%3==1?Optional.empty():"wrong";boolean b=x instanceof Optional;Optional<?> o=(Optional<?>)x;return (b?1:0)+(o==x?2:0);}catch(ClassCastException e){return 9;}}}'''
driver='''import net.minecraft.test.OptionalMapProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("cast")?OptionalMapProbe.cast(n):OptionalMapProbe.run(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-optional-map-') as t:
 d=pathlib.Path(t);(d/'OptionalMapProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'OptionalMapProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 seq=list(range(-40,41))
 for method in ['run','cast']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/OptionalMapProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
  j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',method,*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/method),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
  if j!=n:raise AssertionError((method,j,n))
 print(f'OK: {len(seq)*2} resultados Optional.map y cast/instanceof Optional frente a Java')
