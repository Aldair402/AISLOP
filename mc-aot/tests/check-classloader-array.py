#!/usr/bin/env python3
"""ClassLoader[] solo con el loader de aplicación modelado y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class LoaderArrayProbe {
 public static int run(int n){try{ClassLoader[] a=new ClassLoader[n%5-1];if(a.length==0)return 1;ClassLoader loader=LoaderArrayProbe.class.getClassLoader();a[0]=loader;Object[] alias=a;if(n%3==0)alias[0]=null;if(n%4==0)alias[0]="invalid";return a[0]==loader?2:a[0]==null?3:4;}catch(NegativeArraySizeException e){return 10;}catch(ArrayStoreException e){return 11;}}
 public static int cast(int n){try{Object o=n%3==0?null:n%3==1?LoaderArrayProbe.class.getClassLoader():"wrong";ClassLoader c=(ClassLoader)o;return (o instanceof ClassLoader?1:0)+(c==o?2:0);}catch(ClassCastException e){return 9;}}
 public static int copy(int n){ClassLoader loader=LoaderArrayProbe.class.getClassLoader();ClassLoader[] a=new ClassLoader[3];Object[] src={loader,null,"bad"};try{System.arraycopy(src,0,a,0,n%4);return (a[0]==loader?1:0)+(a[1]==null?2:0);}catch(ArrayStoreException e){return (a[0]==loader?10:0)+(a[1]==null?20:0);}}
}'''
driver='''import net.minecraft.test.LoaderArrayProbe;public class LoaderArrayDriver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("copy")?LoaderArrayProbe.copy(n):a[0].equals("cast")?LoaderArrayProbe.cast(n):LoaderArrayProbe.run(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-loaderarray-') as tmp:
 d=pathlib.Path(tmp);(d/'LoaderArrayProbe.java').write_text(source);(d/'LoaderArrayDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LoaderArrayProbe.java'),str(d/'LoaderArrayDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 total=0
 for method,vals in [('run',list(range(-5,81))),('copy',list(range(80))),('cast',list(range(81)))]:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LoaderArrayProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError(p.stderr)
  java=subprocess.run([str(jdk/'java'),'-cp',str(d),'LoaderArrayDriver',method,*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
  if native.returncode or java.stdout!=native.stdout:raise AssertionError((method,java.stdout,native.stdout,native.stderr))
  total+=len(vals)
 print(f'OK: {total} resultados ClassLoader[] con loader de aplicación/null, límites, ArrayStoreException, arraycopy parcial y casts')
