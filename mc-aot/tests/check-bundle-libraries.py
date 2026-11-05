#!/usr/bin/env python3
"""Resuelve clases en libraries.list, verifica hashes y respeta el orden del classpath."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
lib='''package org.example.fixture;public class Helper{static int bias=7;public static int calc(int n){return n*3+bias;}}'''
shadow='''package org.example.fixture;public class Helper{static int bias=100;public static int calc(int n){return n*5+bias;}}'''
app='''package net.minecraft.test;import org.example.fixture.Helper;public class App{public static int run(int n){return Helper.calc(n);}}'''
driver='''import net.minecraft.test.App;public class Driver{public static void main(String[] a){for(String s:a)System.out.println(App.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-library-bundle-') as t:
 d=pathlib.Path(t);(d/'Helper.java').write_text(lib);(d/'App.java').write_text(app);(d/'Driver.java').write_text(driver)
 libdir=d/'lib';versiondir=d/'version';other=d/'shadow';libdir.mkdir();versiondir.mkdir();other.mkdir()
 subprocess.run([str(jdk/'javac'),'-d',str(libdir),str(d/'Helper.java')],check=True)
 subprocess.run([str(jdk/'javac'),'-cp',str(libdir),'-d',str(versiondir),str(d/'App.java'),str(d/'Driver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'lib.jar'),'-C',str(libdir),'.'],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'version.jar'),'-C',str(versiondir),'.'],check=True)
 (d/'Helper.java').write_text(shadow);subprocess.run([str(jdk/'javac'),'-d',str(other),str(d/'Helper.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'version-shadow.jar'),'-C',str(versiondir),'.','-C',str(other),'.'],check=True)
 def bundle(path,version,bad=False,unsafe=False):
  vd=version.read_bytes();ld=(d/'lib.jar').read_bytes();vn='v/server.jar';ln='lib/helper.jar';hashv=hashlib.sha256(vd).hexdigest();hashl=('0'*64 if bad else hashlib.sha256(ld).hexdigest())
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('META-INF/versions.list',f'{hashv}\tversion\t{vn}\n');z.writestr('META-INF/versions/'+vn,vd)
   z.writestr('META-INF/libraries.list',f'{hashl}\thelper\t'+('../evil.jar' if unsafe else ln)+'\n');z.writestr('META-INF/libraries/'+ln,ld)
 vals=[-1000,-1,0,1,42,2147483647];comparisons=0
 for label,version in [('normal',d/'version.jar'),('shadow',d/'version-shadow.jar')]:
  bundle(d/(label+'.jar'),version);out=d/(label+'-native')
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/(label+'.jar')),'net/minecraft/test/App',str(out),'run','(I)I'],capture_output=True,text=True)
  if p.returncode:raise RuntimeError((label,p.stderr))
  java=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(version),str(d/'lib.jar')]),'Driver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
  args=sum((['0',str(n)] for n in vals),[]);native=subprocess.run([str(out),*args],capture_output=True,text=True,check=True).stdout
  if java!=native:raise AssertionError((label,java,native));
  comparisons+=len(vals)
 for label,bad,unsafe,expected in [('bad-hash',True,False,'SHA-256 incorrecto'),('path',False,True,'entrada insegura')]:
  bundle(d/(label+'.jar'),d/'version.jar',bad,unsafe);out=d/(label+'-native')
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/(label+'.jar')),'net/minecraft/test/App',str(out),'run','(I)I'],capture_output=True,text=True)
  if p.returncode==0 or expected not in p.stderr or out.exists():raise AssertionError((label,p.returncode,p.stderr))
 print(f'OK: {comparisons} llamadas Java; búsqueda de biblioteca, precedencia versión/biblioteca, inicialización y dos bundle malformados rechazados')
