#!/usr/bin/env python3
"""ObjectMethods.equals integral: identidad, null, tipos y campos contra Java 25."""
import os
import pathlib
import random
import subprocess
import tempfile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
official = root.parent / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
source = '''package net.minecraft.test;
import net.minecraft.network.protocol.game.VecDelta.Stepped.DeltaStep;
public class RecordsEqual {
 public record Mixed(int i,long l,boolean b,short s,char c,byte x) {}
 public record Empty() {}
 public record Decimal(float x) {}
 public static int mixed(int a,int b,int option) {
   Mixed left=new Mixed(a,((long)a)*10000000000L,(a&1)!=0,(short)a,(char)a,(byte)a);
   Object other;
   if(option==0) other=null;
   else if(option==1) other=left;
   else if(option==2) other=new Mixed(b,((long)b)*10000000000L,(b&1)!=0,(short)b,(char)b,(byte)b);
   else if(option==3) other=new Empty();
   else other="other";
   return left.equals(other)?1:0;
 }
 public static int empty(int option) {Empty e=new Empty();return e.equals(option==0?null:new Empty())?1:0;}
 public static int vanilla(int a,int b,int option) {
   DeltaStep left=new DeltaStep((short)a,(short)(a+1),(short)(a-1),a);
   Object other=option==0?null:option==1?left:new DeltaStep((short)b,(short)(b+1),(short)(b-1),b);
   return left.equals(other)?1:0;
 }
 public static int decimal(int a) {return new Decimal(Float.intBitsToFloat(a)).equals(new Decimal(0))?1:0;}
}'''
driver = '''import net.minecraft.test.RecordsEqual;
public class Oracle {
 public static void main(String[] args){
  for(int i=0;i<args.length;){int op=Integer.parseInt(args[i++]);
   if(op==0)System.out.println(RecordsEqual.mixed(Integer.parseInt(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++])));
   else if(op==1)System.out.println(RecordsEqual.empty(Integer.parseInt(args[i++])));
   else System.out.println(RecordsEqual.vanilla(Integer.parseInt(args[i++]),Integer.parseInt(args[i++]),Integer.parseInt(args[i++])));
  }
 }
}'''
def run(args, **kw):
 return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=180, **kw)

with tempfile.TemporaryDirectory(prefix='record-equals-') as tmp:
 d=pathlib.Path(tmp); (d/'RecordsEqual.java').write_text(source); (d/'Oracle.java').write_text(driver)
 r=run([jdk/'javac','-cp',official,'-d',d,d/'RecordsEqual.java',d/'Oracle.java']);assert r.returncode==0,r.stderr
 jar=d/'fixture.jar'
 with zipfile.ZipFile(jar,'w') as out:
  for path in (d/'net').rglob('*.class'):out.write(path,path.relative_to(d).as_posix())
  name='net/minecraft/network/protocol/game/VecDelta$Stepped$DeltaStep.class'
  with zipfile.ZipFile(official) as src:out.writestr(name,src.read(name))
 binary=d/'native'
 r=run([compiler,'multi-static-demo',jar,'net/minecraft/test/RecordsEqual',binary,'mixed','(III)I','empty','(I)I','vanilla','(III)I'])
 assert r.returncode==0,r.stderr
 cases=[]
 for option in range(5):
  for a,b in [(0,0),(0,1),(-1,-1),(-2147483648,2147483647),(65536,0)]:cases.append(('0',str(a),str(b),str(option)))
 for option in range(2):cases.append(('1',str(option)))
 rng=random.Random(20261109)
 for i in range(100):
  a=rng.randint(-2147483648,2147483647); b=a if i%2 else rng.randint(-2147483648,2147483647)
  cases.append(('2',str(a),str(b),str(i%3)))
 args=[x for c in cases for x in c]
 java=run([jdk/'java','-cp',f'{d}{os.pathsep}{official}','Oracle',*args])
 native=run([binary,*args],env=dict(os.environ,PATH='/nonexistent'))
 assert java.returncode==native.returncode==0,(java.stderr,native.stderr)
 assert len(java.stdout.splitlines())==len(cases) and java.stdout==native.stdout,(java.stdout,native.stdout)
 bad=d/'bad';r=run([compiler,'multi-static-demo',jar,'net/minecraft/test/RecordsEqual',bad,'decimal','(I)I'])
 assert r.returncode!=0 and 'ObjectMethods.equals: tipo no soportado: F' in r.stderr and not bad.exists(),r.stderr
 print(f'OK: {len(cases)} equals de records vacíos/integrales/DeltaStep vanilla == Java 25; null, identidad, tipo distinto y cambios; float rechazado; sin JVM')
