#!/usr/bin/env python3
"""String.trim según rango Java <= U+0020 e identidad cuando no cambia."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class TrimDemo{public static int run(String s,int n){try{switch(n){case 0:return s.trim().length();case 1:return s.trim()==s?1:0;case 2:return s.trim()==""?2:0;case 3:return "\000 x\t".trim().equals("x")?3:0;default:return 99;}}catch(NullPointerException e){return 104;}}}'''
driver='''import net.minecraft.test.TrimDemo;public class TrimDriver{public static void main(String[]a){for(int i=0;i<a.length;i+=2)System.out.println(TrimDemo.run(a[i].equals("@null")?null:a[i],Integer.parseInt(a[i+1])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-trim-') as t:
 d=pathlib.Path(t);(d/'TrimDemo.java').write_text(source);(d/'TrimDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'TrimDemo.java'),str(d/'TrimDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/TrimDemo',str(d/'native'),'run','(Ljava/lang/String;I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=[(s,str(n)) for s in ('@null','abc',' x ','','  ','\tX\n',' a ','á') for n in range(4)]*5;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'TrimDriver',*[v for pair in seq for v in pair]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for s,n in seq for v in ('0','null' if s=='@null' else 's:'+s,n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} resultados Java de trim, identidad, controles ASCII y Unicode')
