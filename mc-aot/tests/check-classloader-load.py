#!/usr/bin/env python3
"""Carga cerrada de clases precompiladas: identidad y ausencia de inicialización."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class LoaderDemo {
 static int count=1;static int bump(){return ++count;}
 static class Target {static int v=bump();}interface Mark {int x=bump();}
 public static int run(int n){try {ClassLoader l=LoaderDemo.class.getClassLoader();switch(n){
 case 0:Class<?> a=l.loadClass("net.minecraft.test.LoaderDemo$Target");return (a==Target.class?1:0)+count*100;
 case 1:Class<?> b=l.loadClass("net.minecraft.test.LoaderDemo$Mark");return (b==Mark.class?2:0)+count*100;
 case 2:return (l.loadClass("java.lang.String")==String.class?3:0)+count*100;
 case 3:return Target.v*100+count;
 case 4:return l.loadClass(null)==null?0:-1;
 case 5:ClassLoader z=null;return z.loadClass("net.minecraft.test.LoaderDemo")==null?0:-1;
 case 6:return l.loadClass("not.real.Missing")==null?0:-1;
 default:return count;
 }}catch(NullPointerException e){return 101;}catch(ClassNotFoundException e){return 102;}}
}'''
driver='''import net.minecraft.test.LoaderDemo;public class LoaderDriver{public static void main(String[] a){for(String s:a)System.out.println(LoaderDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-loader-load-') as t:
 d=pathlib.Path(t);(d/'LoaderDemo.java').write_text(source);(d/'LoaderDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LoaderDemo.java'),str(d/'LoaderDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LoaderDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['0','1','2','4','5','3','0','1','2']*10+['-1'];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'LoaderDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','6'],capture_output=True,text=True)
 if p.returncode!=2 or 'clase no precompilada o desconocida' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} cargas Java de clases/literales precompilados, identidad, null e inicialización diferida; desconocida aborta explícitamente')
