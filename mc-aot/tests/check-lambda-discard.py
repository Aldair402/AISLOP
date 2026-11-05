#!/usr/bin/env python3
"""Metafactory con retorno de implementación descartado por un SAM void."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.function.*;import java.util.*;class Box{int n;Box(int v){n=v;}int add(int x){n+=x;return n;}static int ignored(String x){return x.length();}}public class LambdaDiscardDemo{public static int run(int n){Box box=new Box(n);BiConsumer<Box,Integer> f=Box::add;f.accept(box,2);Consumer<String> s=Box::ignored;s.accept("hello");Consumer<Integer> c=Box::new;c.accept(5);Supplier<StringBuilder> b=StringBuilder::new;Supplier<Map> m=HashMap::new;return box.n+b.get().append("abc").length()+m.get().size();}}'''
driver='''import net.minecraft.test.LambdaDiscardDemo;public class LDriver{public static void main(String[]a){for(String x:a)System.out.println(LambdaDiscardDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-lambda-discard-') as t:
 d=pathlib.Path(t);(d/'LambdaDiscardDemo.java').write_text(src);(d/'LDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LambdaDiscardDemo.java'),str(d/'LDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LambdaDiscardDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(60));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'LDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 env={**os.environ,'MC_AOT_GUARD_MINECRAFT_LAMBDAS':'1'}
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LambdaDiscardDemo',str(d/'guarded'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'guarded'),'0','1'],capture_output=True,text=True,env=env)
 if p.returncode==0 or 'lambda Minecraft no compilada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 60 adaptaciones lambda a void y guarda explícita del modo diagnóstico')
