#!/usr/bin/env python3
"""Double.valueOf/doubleValue y casts, con bits extremos/NaN."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.io.*;public class DoubleBoxProbe{public static long run(long bits){double d=Double.longBitsToDouble(bits);Object x=Double.valueOf(d);if(!(x instanceof Double)||!(x instanceof Number)||!(x instanceof Serializable)||x.getClass()!=Double.class)return 11;Double y=(Double)x;if(y==Double.valueOf(d))return 12;return Double.doubleToRawLongBits(y.doubleValue());}public static int nul(int n){try{Object x=n==0?null:"x";Double d=(Double)x;return d.doubleValue()==0?0:1;}catch(NullPointerException e){return 7;}catch(ClassCastException e){return 8;}}}'''
driver='''import net.minecraft.test.DoubleBoxProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++)System.out.println(a[0].equals("run")?DoubleBoxProbe.run(Long.parseLong(a[i])):DoubleBoxProbe.nul(Integer.parseInt(a[i])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-double-box-') as t:
 d=pathlib.Path(t);(d/'DoubleBoxProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DoubleBoxProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method,desc):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DoubleBoxProbe',str(d/method),method,desc],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((method,p.stderr))
 rng=random.Random(250);bits=[0,1,0x7ff0000000000000,0x7ff8000000000001,0x8000000000000000,0xfff0000000000000]+[rng.getrandbits(64) for _ in range(100)];seq=[v if v<2**63 else v-2**64 for v in bits]
 for method,desc,vals in [('run','(J)J',seq),('nul','(I)I',[0,1])]:
  compile(method,desc);j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',method,*map(str,vals)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/method),*[v for x in vals for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
  if j!=n:raise AssertionError((method,j,n))
 print(f'OK: {len(seq)+2} valores Double boxing/raw bits/casts/clase/null; sin formato ni equals general')
