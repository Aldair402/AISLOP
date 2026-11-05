#!/usr/bin/env python3
"""El backend numérico debe rechazar características JVM que aún no implementa."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class NumericGuards {
 public static long recurse(long n){return n==0?0:recurse(n-1);}
 public static synchronized long locked(long n){return n+1;}
 public static long array(long n){return new long[][]{{n}}[0][0];}
 public static long caught(long n){try{return 1/n;}catch(OutOfMemoryError e){return 0;}}
 public static long external(long n){return n+System.nanoTime();}
}'''
with tempfile.TemporaryDirectory(prefix='mc-numeric-guards-') as tmp:
 d=pathlib.Path(tmp);(d/'NumericGuards.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'NumericGuards.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cases=[('recurse','recursión'),('locked','synchronized'),('array','anewarray no soportado'),('caught','tipo catch no soportado'),('external','invokestatic no soportado')]
 for name,expected in cases:
  out=d/name
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'fixture.jar'),'net/minecraft/test/NumericGuards',name,'(J)J',str(out)],capture_output=True,text=True)
  if p.returncode==0 or expected not in p.stderr or out.exists():raise AssertionError((name,p.returncode,p.stdout,p.stderr,out.exists()))
 print(f'OK: {len(cases)} rechazos: recursión, synchronized, arrays multidimensionales, tipo catch desconocido y llamada externa')
