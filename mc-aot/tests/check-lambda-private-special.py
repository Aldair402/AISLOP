#!/usr/bin/env python3
"""Java 8 REF_invokeSpecial a métodos privados con receptor capturado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.function.*;public class SpecialLambdaProbe{final int base;SpecialLambdaProbe(int n){base=n;}IntUnaryOperator op(int k){return x->base+k+x;}Function<String,String> text(String s){return x->s+x+base;}private String decorate(String s){return s+base;}Function<String,String> bound(){return this::decorate;}public static int run(int n){SpecialLambdaProbe a=new SpecialLambdaProbe(n),b=new SpecialLambdaProbe(n+1);IntUnaryOperator f=a.op(3),g=b.op(7);return f.applyAsInt(n)+g.applyAsInt(n+1);}public static int string(int n){SpecialLambdaProbe a=new SpecialLambdaProbe(n);return a.text("pre").apply("hi").hashCode();}public static int bound(int n){SpecialLambdaProbe a=new SpecialLambdaProbe(n);return a.bound().apply("hello").hashCode();}public static int nullable(int n){try{SpecialLambdaProbe p=(n&1)==0?null:new SpecialLambdaProbe(n);Function<String,String> f=p::decorate;return f.apply("z").length();}catch(NullPointerException e){return 7;}}}'''
driver='''import net.minecraft.test.SpecialLambdaProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("run")?SpecialLambdaProbe.run(n):a[0].equals("bound")?SpecialLambdaProbe.bound(n):a[0].equals("nullable")?SpecialLambdaProbe.nullable(n):SpecialLambdaProbe.string(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-special-lambda-') as t:
 d=pathlib.Path(t);(d/'SpecialLambdaProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'--release','8','-Xlint:-options','-d',str(d),str(d/'SpecialLambdaProbe.java'),str(d/'Driver.java')],check=True);out=subprocess.run([str(jdk/'javap'),'-v','-p','-cp',str(d),'net.minecraft.test.SpecialLambdaProbe'],capture_output=True,text=True,check=True).stdout
 if 'REF_invokeSpecial net/minecraft/test/SpecialLambdaProbe.lambda$' not in out:raise AssertionError('fixture no usa REF_7')
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 seq=list(range(-40,41))
 for method in ['run','string','bound','nullable']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SpecialLambdaProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
  j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',method,*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/method),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
  if j!=n:raise AssertionError((method,j,n))
 print(f'OK: {len(seq)*4} resultados REF_7 privado y sintético, receptores/capturas, int y String')
