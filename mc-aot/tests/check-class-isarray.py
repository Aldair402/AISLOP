#!/usr/bin/env python3
"""Class.isArray para clases y arrays modelados."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class IsArrayProbe{public static int run(int n){try{Object x=n%4==0?null:n%4==1?new int[n&7]:n%4==2?new String[n&7]:"x";return x.getClass().isArray()?1:2;}catch(NullPointerException e){return 3;}}}'''
driver='''import net.minecraft.test.IsArrayProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(IsArrayProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-class-isarray-') as t:
 d=pathlib.Path(t);(d/'IsArrayProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'IsArrayProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/IsArrayProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Class.isArray para int[], String[], String y null')
