#!/usr/bin/env python3
"""Integer.toHexString: minúsculas sin signo en dos complementos."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class HexProbe{public static int hash(int n){return Integer.toHexString(n).hashCode();}public static int len(int n){return Integer.toHexString(n).length();}public static int value(int n){String s=Integer.toHexString(n);return Integer.parseUnsignedInt(s,16);}}'''
driver='''import net.minecraft.test.HexProbe;public class Driver{public static void main(String[]a){for(String n:a){int x=Integer.parseInt(n);System.out.println(HexProbe.hash(x));System.out.println(HexProbe.len(x));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-integer-hex-') as t:
 d=pathlib.Path(t);(d/'HexProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'HexProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 for method in ('hash','len'):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/HexProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(175);seq=[0,1,15,16,255,256,-1,-16,-2147483648,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(250)]
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout.splitlines();outs=[]
 for name in ('hash','len'):outs.append(subprocess.run([str(d/name),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines())
 n=[value for pair in zip(*outs) for value in pair]
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} entradas y {len(j)} resultados de Integer.toHexString contra Java 25')
