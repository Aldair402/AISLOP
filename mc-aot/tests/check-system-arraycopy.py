#!/usr/bin/env python3
"""Copia de arrays: tipos, solapamiento, fallos y copia parcial."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;public class CopyDemo{public static int run(int n){try{switch(n%8){case 0:{int[] a={1,2,3,4};System.arraycopy(a,0,a,1,3);return a[0]*1000+a[1]*100+a[2]*10+a[3];}case 1:{int[] a={1,2,3,4};System.arraycopy(a,1,a,0,3);return a[0]*1000+a[1]*100+a[2]*10+a[3];}case 2:{Object[] a={"a",Integer.valueOf(9),"zzz"};String[] b={"old","old","old"};try{System.arraycopy(a,0,b,0,3);}catch(ArrayStoreException e){return b[0].length()*10+b[1].length();}return 0;}case 3:System.arraycopy(new int[2],0,new byte[2],0,0);return 3;case 4:System.arraycopy(new int[2],1,new int[2],0,2);return 4;case 5:System.arraycopy(null,0,new int[2],0,1);return 5;case 6:System.arraycopy("x",0,new int[2],0,0);return 6;default:{String[] a={"a","bb","ccc"};Object[] b=new Object[3];System.arraycopy(a,0,b,0,3);return ((String)b[2]).length();}}}catch(ArrayStoreException e){return 71;}catch(IndexOutOfBoundsException e){return 72;}catch(NullPointerException e){return 73;}}}'''
driver='''import net.minecraft.test.CopyDemo;public class CopyDriver{public static void main(String[]a){for(String x:a)System.out.println(CopyDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-arraycopy-') as t:
 d=pathlib.Path(t);(d/'CopyDemo.java').write_text(src);(d/'CopyDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CopyDemo.java'),str(d/'CopyDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CopyDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(160));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'CopyDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 160 copias, fallos, solapamientos y copia parcial comparados con Java')
