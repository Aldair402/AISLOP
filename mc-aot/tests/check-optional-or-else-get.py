#!/usr/bin/env python3
"""Optional.orElseGet: supplier solo para vacío y excepciones propagadas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.function.Supplier;
public class OptionalProbe{static int calls;static String fallback(){calls++;return "fallback";}static String throwsIt(){calls++;throw new IllegalArgumentException();}
 public static int run(int n){calls=0;try{Optional<String> o=(n&1)==0?Optional.of("value"):Optional.empty();Supplier<String> s=(n&2)!=0?null:(n&4)!=0?OptionalProbe::throwsIt:OptionalProbe::fallback;String x=o.orElseGet(s);return calls*10+(x==null?0:x.equals("value")?1:2);}catch(NullPointerException e){return 50+calls;}catch(IllegalArgumentException e){return 60+calls;}}
 public static int nullResult(int n){String v=Optional.<String>empty().orElseGet(()->null);return v==null?1:0;}}
'''
driver='''import net.minecraft.test.OptionalProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(OptionalProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-optional-get-') as t:
 d=pathlib.Path(t);(d/'OptionalProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'OptionalProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/OptionalProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'run'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 compile('nullResult');p=subprocess.run([str(d/'nullResult'),'0','0'],capture_output=True,text=True,check=True)
 if p.stdout!='1\n':raise AssertionError((p.stdout,p.stderr))
 print(f'OK: {len(seq)+1} resultados Optional.orElseGet frente a Java, evaluación diferida, null y excepción')
