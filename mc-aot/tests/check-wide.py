#!/usr/bin/env python3
"""Genera >255 variables para comprobar wide loads/stores/iinc en bytecode javac."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
variables='\n'.join(f'    int a{i}=x+{i};' for i in range(260))
source='''package net.minecraft.test;
public class WideFixture {
 public static long wide(int x) {
'''+variables+'''
    long k=a259; a259+=300; a259-=301; k+=a259; return k;
 }
 public static void main(String[] args) {for(String s:args)System.out.println(wide(Integer.parseInt(s)));}
}'''
with tempfile.TemporaryDirectory(prefix='mc-wide-') as tmp:
 d=pathlib.Path(tmp);(d/'WideFixture.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'WideFixture.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 code=subprocess.run([str(jdk/'javap'),'-p','-c','-classpath',str(d),'net.minecraft.test.WideFixture'],capture_output=True,text=True,check=True).stdout
 for name in ('istore_w','iload_w','lstore_w','lload_w','iinc_w'):
  if name not in code:raise AssertionError('javac no emitió '+name)
 if 'iinc_w        260, 300' not in code or 'iinc_w        260, -301' not in code:raise AssertionError('faltan incrementos wide positivos/negativos')
 subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'fixture.jar'),'net/minecraft/test/WideFixture','wide','(I)J',str(d/'wide')],capture_output=True,text=True,check=True)
 values=[-2147483648,-1000,-260,-1,0,1,1000,2147483647]
 ref=subprocess.run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.WideFixture',*map(str,values)],capture_output=True,text=True,check=True).stdout.splitlines()
 for n,want in zip(values,ref):
  got=subprocess.run([str(d/'wide'),str(n)],capture_output=True,text=True,check=True).stdout.strip()
  if got!=want:raise AssertionError((n,got,want))
 print(f'OK: wide con 260 locales; 5 variantes y {len(values)} resultados coinciden con Java 25')
