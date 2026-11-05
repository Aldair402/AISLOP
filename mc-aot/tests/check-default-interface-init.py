#!/usr/bin/env python3
"""Inicialización de superinterfaces con defaults; despacho default sigue bajo guarda."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class Trace {static int n;static int mark(int x){n=n*10+x;return x;}}
interface Root {int ID=Trace.mark(1);default int f(){return 10;}}
interface Mid extends Root {int ID=Trace.mark(2);}
interface Left extends Mid {int ID=Trace.mark(3);default int g(){return 20;}}
interface Right extends Root {int ID=Trace.mark(4);default int h(){return 30;}}
interface PrivateOnly {int ID=Trace.mark(7);private int p(){return 5;}}
class Impl implements Left,Right,PrivateOnly {static int ID=Trace.mark(5);public int f(){return 11;}public int g(){return 21;}public int h(){return 31;}}
class OnlyDefault implements Root {}
class Fail {static int z;static int go(){return 1/z;}}
interface Broken {int ID=Fail.go();default int f(){return 8;}}
class Failure implements Broken {}
interface Plain extends Root {int ID=Trace.mark(6);}
public class DefaultInitDemo {public static int run(int n){switch(n){case 0:Impl i=new Impl();return Trace.n;case 1:return Mid.ID*100000+Trace.n;case 2:Left x=new Impl();return x.f()+x.g();case 3:return PrivateOnly.ID*100000+Trace.n;case 4:return Plain.ID*100000+Trace.n;case 5:Root d=new OnlyDefault();return d.f();case 6:try{new Failure();return 0;}catch(ExceptionInInitializerError e){return 106;}catch(NoClassDefFoundError e){return 107;}default:return Trace.n;}}}
'''
driver='''import net.minecraft.test.DefaultInitDemo;public class DefaultDriver{public static void main(String[]a){for(String s:a)System.out.println(DefaultInitDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-default-init-') as t:
 d=pathlib.Path(t);(d/'DefaultInitDemo.java').write_text(source);(d/'DefaultDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DefaultInitDemo.java'),str(d/'DefaultDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DefaultInitDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 for ops in [('0','1','2','3','4','0'),('4','0','1','3'),('6','6')]:
  java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DefaultDriver',*ops],capture_output=True,text=True,check=True).stdout
  native=subprocess.run([str(d/'native'),*[v for n in ops for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
  if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','5'],capture_output=True,text=True)
 if p.returncode!=2 or 'invokeinterface: tipo o método no precompilado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: inicialización Java ordenada de interfaces con defaults, diamante, método privado (JVM), acceso directo y despacho directo; default heredado aborta explícitamente')
