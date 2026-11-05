#!/usr/bin/env python3
"""Adaptación lambda de Object a Class: tipo, null y llamada real."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.function.Function;public class LambdaClassProbe{@SuppressWarnings({"rawtypes","unchecked"}) public static int run(int n){try{Function<Class<?>,String> f=x->x.getName();Function raw=f;Object o=n%3==0?null:n%3==1?LambdaClassProbe.class:"bad";String s=(String)raw.apply(o);return s.equals("net.minecraft.test.LambdaClassProbe")?1:0;}catch(ClassCastException e){return 2;}catch(NullPointerException e){return 3;}}}'''
driver='''import net.minecraft.test.LambdaClassProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(LambdaClassProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-lambda-class-') as t:
 d=pathlib.Path(t);(d/'LambdaClassProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LambdaClassProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LambdaClassProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} resultados lambda Class con adaptación desde Object, null y ClassCastException')
