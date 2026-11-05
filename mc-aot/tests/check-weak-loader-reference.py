#!/usr/bin/env python3
"""WeakReference únicamente de null o el cargador de aplicación permanentemente arraigado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.lang.ref.*;public class WeakLoaderProbe{
 public static int run(int n){try{ClassLoader l=WeakLoaderProbe.class.getClassLoader();WeakReference<ClassLoader> a=new WeakReference<>((n&1)==0?l:null);Reference<ClassLoader> b=a;int r=(a.get()==l?1:0)+(b.get()==null?2:0);if((n&2)!=0)a.clear();if((n&4)!=0)b.clear();return r+(a.get()==l?4:0)+(b.get()==null?8:0);}catch(NullPointerException e){return 100;}}
 public static int bad(int n){return new WeakReference<>(new Object()).get()==null?1:0;}
 public static int missing(int n){WeakReference<ClassLoader> r=null;try{r.clear();return 1;}catch(NullPointerException e){return 9;}}
}'''
driver='''import net.minecraft.test.WeakLoaderProbe;public class WeakLoaderDriver{public static void main(String[]a){for(String n:a)System.out.println(WeakLoaderProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-weak-loader-') as tmp:
 d=pathlib.Path(tmp);(d/'WeakLoaderProbe.java').write_text(source);(d/'WeakLoaderDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'WeakLoaderProbe.java'),str(d/'WeakLoaderDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/WeakLoaderProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'WeakLoaderDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('missing')
 if p.returncode:raise RuntimeError(p.stderr)
 n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
 if n.returncode or n.stdout!='9\n':raise AssertionError(('null',n.stdout,n.stderr))
 p=compile('bad')
 if p.returncode:raise RuntimeError(p.stderr)
 n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
 if n.returncode==0 or 'solo ClassLoader de aplicación/null soportado' not in n.stderr:raise AssertionError(('unrooted referent',n.stderr))
 print(f'OK: {len(vals)+1} resultados WeakReference de loader/null, get/clear y receptor null; referentes arbitrarios abortan')
