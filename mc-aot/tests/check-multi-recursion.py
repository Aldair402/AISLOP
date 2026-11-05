#!/usr/bin/env python3
"""Recursión multiclase directa/mutua, métodos de instancia y desenrollado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;class RecurObject{int f(int n){return n<=1?1:n*f(n-1);}}
public class RecurDemo {static RecurObject obj=new RecurObject();static int a(int n){return n==0?1:b(n-1)+1;}static int b(int n){return n==0?2:a(n-1)+2;}static int throwsAt(int n){return n==0?1/n:throwsAt(n-1);}public static int run(int n){try{if(n<0)return throwsAt(-n);if(n<20)return obj.f(n);return a(n-20);}catch(ArithmeticException e){return 101;}}}
'''
driver='''import net.minecraft.test.RecurDemo;public class RecurDriver{public static void main(String[]a){for(String s:a)System.out.println(RecurDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-recursion-') as t:
 d=pathlib.Path(t);(d/'RecurDemo.java').write_text(source);(d/'RecurDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RecurDemo.java'),str(d/'RecurDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RecurDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(i) for i in range(-30,90)]*2;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'RecurDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','500'],capture_output=True,text=True)
 if p.returncode!=2 or 'límite experimental de recursión excedido' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} resultados Java de recursión mutua e instancia, excepciones y desenrollado; profundidad excesiva aborta')
