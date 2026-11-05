#!/usr/bin/env python3
"""Diferencial JVM/nativo de dos switches reales y tres métodos artificiales."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parent.parent
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';inner=root/'downloads/server-26.3-inner.jar'
fixture='''package net.minecraft.test;
public class SwitchFixture {
 public static int table(int x) {
   int out=0;
   switch(x) {case -2:out=100;break; case -1:out=200;break; case 0:out=300;break;
     case 1:out=400; case 2:out+=7;break; default:out=-999;}
   return out;
 }
 public static int lookup(int x) {
   switch(x) {case -2147483648:return 101;case -100:return -102;case 5000:return 103;
     case 2147483647:return 104; default:return -105;}
 }
 public static int nested(int x) {return lookup(x+1);}
}'''
with tempfile.TemporaryDirectory(prefix='mc-switch-') as tmp:
 d=pathlib.Path(tmp);(d/'SwitchFixture.java').write_text(fixture)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SwitchFixture.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 subprocess.run([str(jdk/'javac'),'-cp',str(d),'-d',str(d),str(root/'graal-test/SwitchReference.java')],check=True)
 bytecode=subprocess.run([str(jdk/'javap'),'-p','-c','-classpath',str(d/'test.jar'),'net.minecraft.test.SwitchFixture'],capture_output=True,text=True,check=True).stdout
 assert 'tableswitch' in bytecode and 'lookupswitch' in bytecode
 methods=[(inner,'net/minecraft/util/PngInfo','validateBitDepth','(I)Z'),(inner,'net/minecraft/util/PngInfo','validateColorType','(I)Z'),*[ (d/'test.jar','net/minecraft/test/SwitchFixture',x,'(I)I') for x in ('table','lookup','nested')]]
 for jar,cls,meth,desc in methods:
  subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(jar),cls,meth,desc,str(d/meth)],capture_output=True,text=True,check=True)
 rng=random.Random(5489);values=list(range(-20,22))+[-2147483648,-2147483647,-100,-101,-99,4999,5000,5001,2147483646,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(100)]
 ref=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'SwitchReference'],input=''.join(str(v)+'\n' for v in values),capture_output=True,text=True,check=True).stdout.splitlines()
 assert len(ref)==len(values)
 for v,row in zip(values,ref):
  for (_,_,method,_),expected in zip(methods,row.split(',')):
   proc=subprocess.run([str(d/method),str(v)],capture_output=True,text=True,check=True)
   if proc.stdout.strip()!=expected:raise AssertionError((v,method,proc.stdout,expected))
 print(f'OK: {len(values)*len(methods)} resultados de switches coinciden con Java 25; 2 métodos reales y 3 sintéticos')
