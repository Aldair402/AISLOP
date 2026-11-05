#!/usr/bin/env python3
"""Prueba identidad, alias con mutación y despacho entre dos clases Java sintéticas."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
interface Counter { int get(); int bump(); default int twice(){return get()+get();} }
class One implements Counter {
 int value; One(int v){value=v;} public int get(){return value;}
 public int bump(){value=value+1;return value;}
}
class Two implements Counter {
 int value; Two(int v){value=v;} public int get(){return value;}
 public int bump(){value=value+2;return value;}
}
public class MultiCases {
 public static void main(String[] args) throws Exception {
  var in=new java.io.BufferedReader(new java.io.InputStreamReader(System.in));
  for(String s;(s=in.readLine())!=null;){
   String[] v=s.split(","); Counter a=new One(Integer.parseInt(v[0])),b=new Two(Integer.parseInt(v[1])),alias=a;
   System.out.println("0,1,2,"+alias.bump()+","+a.get()+","+a.twice()+","+b.bump()+","+b.get()+","+(a==alias?1:0)+","+(a==b?1:0));
  }
 }
}'''
with tempfile.TemporaryDirectory(prefix='mc-multi-tests-') as tmp:
 d=pathlib.Path(tmp);(d/'MultiCases.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MultiCases.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 native=d/'native';base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-demo',str(d/'fixture.jar'),'net/minecraft/test/One','net/minecraft/test/Two','net/minecraft/test/Counter','twice',str(native)]
 out=subprocess.run(base,capture_output=True,text=True)
 if out.returncode!=0:raise RuntimeError(out.stderr)
 rng=random.Random(88);cases=[(-2147483648,2147483647),(0,0),(2147483647,2147483647),(-1,-2)]+[(rng.randint(-2147483648,2147483647),rng.randint(-2147483648,2147483647)) for _ in range(100)]
 proc=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar'),'net.minecraft.test.MultiCases'],input=''.join(f'{a},{b}\n' for a,b in cases),text=True,capture_output=True,check=True)
 if len(proc.stdout.splitlines())!=len(cases):raise RuntimeError('referencia incompleta')
 for (a,b),expected in zip(cases,proc.stdout.splitlines()):
  cmd=['new','0',str(a),'new','1',str(b),'copy','0','call','2','bump','call','0','get','call','0','twice','call','1','bump','call','1','get','eq','0','2','eq','0','1']
  result=subprocess.run([str(native),*cmd],text=True,capture_output=True,check=True)
  actual=','.join(result.stdout.splitlines())
  if actual!=expected:raise AssertionError((a,b,actual,expected))
 print(f'OK: {len(cases)} secuencias; alias con mutación, identidad y despacho de dos clases sintéticas')
