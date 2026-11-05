#!/usr/bin/env python3
"""Rama de loader null inalcanzable para literales de clase del bundle."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class DeadLoader {
 public static int run(int n){ClassLoader l=DeadLoader.class.getClassLoader();if(l==null){Runnable x=()->System.out.println("imposible");x.run();return -1;}return n+11;}
 public static int run2(int n){ClassLoader l=DeadLoader.class.getClassLoader();if(l!=null)return n+13;Runnable x=()->System.out.println("imposible");x.run();return -1;}
 public static int unsupported(ClassLoader l){if(l==null){Runnable x=()->System.out.println("real");x.run();}return 1;}
}'''
driver='''import net.minecraft.test.DeadLoader;public class DeadLoaderDriver{public static void main(String[] a){for(String x:a){int n=Integer.parseInt(x);System.out.println(DeadLoader.run(n));System.out.println(DeadLoader.run2(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-loader-fold-') as t:
 d=pathlib.Path(t);(d/'DeadLoader.java').write_text(source);(d/'DeadLoaderDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DeadLoader.java'),str(d/'DeadLoaderDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DeadLoader']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I','run2','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['-100','0','1','100','2147483647']*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DeadLoaderDriver',*vals],capture_output=True,text=True,check=True).stdout;args=[v for n in vals for v in ('0',n,'1',n)];native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)*2} resultados Java con loader no null e invokedynamic inalcanzable')
