#!/usr/bin/env python3
"""Asegura que el directorio Enum.valueOf es una instantánea y no el array vivo."""
import os,pathlib,subprocess,sys,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';sys.path.insert(0,str(root))
from scan_bytecode import parse
source='''package net.minecraft.test;public enum CacheEnum {ALPHA,BETA;public static CacheEnum[] leak(){return values();}}'''
probe='''package net.minecraft.test;public class CacheProbe{public static int run(int n){if(n==0){CacheEnum a=Enum.valueOf(CacheEnum.class,"ALPHA");CacheEnum.leak()[0]=CacheEnum.BETA;return (Enum.valueOf(CacheEnum.class,"ALPHA")==a?1:0)+(Enum.valueOf(CacheEnum.class,"BETA")==CacheEnum.BETA?2:0);}CacheEnum.leak()[0]=CacheEnum.BETA;try{Enum.valueOf(CacheEnum.class,"ALPHA");return -1;}catch(IllegalArgumentException e){return Enum.valueOf(CacheEnum.class,"BETA")==CacheEnum.BETA?4:-4;}}}'''
driver='''import net.minecraft.test.CacheProbe;public class Driver{public static void main(String[]a){System.out.println(CacheProbe.run(Integer.parseInt(a[0])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-enum-cache-') as t:
 d=pathlib.Path(t)
 for name,src in [('CacheEnum.java',source),('CacheProbe.java',probe),('Driver.java',driver)]:(d/name).write_text(src)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/n) for n in ('CacheEnum.java','CacheProbe.java','Driver.java')]],check=True)
 cls=d/'net/minecraft/test/CacheEnum.class';data=cls.read_bytes();_,methods=parse(data)
 values=next(code for _,name,desc,code in methods if name=='values');leak=next(code for _,name,desc,code in methods if name=='leak')
 assert len(values)==10 and values[0]==0xb2 and len(leak)==4 and leak[0]==0xb8 and leak[3]==0xb0
 old=len(leak).to_bytes(4,'big')+leak;new=len(leak).to_bytes(4,'big')+values[:3]+leak[3:]
 assert data.count(old)==1;cls.write_bytes(data.replace(old,new,1))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CacheProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 for value in (0,1):
  j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',str(value)],capture_output=True,text=True,check=True).stdout
  n=subprocess.run([str(d/'native'),'0',str(value)],capture_output=True,text=True)
  if n.returncode or n.stdout!=j:raise AssertionError((value,j,n.stdout,n.stderr))
 # Mutar el values() canónico a una forma distinta: el traductor compila pero
 # la llamada debe abortar, no tratar la implementación alterada como javac.
 patched=data.replace(len(values).to_bytes(4,'big')+values,len(values).to_bytes(4,'big')+leak[:3]+values[3:],1)
 assert patched!=data;cls.write_bytes(patched)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'altered.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'altered.jar'),'net/minecraft/test/CacheProbe',str(d/'guard'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'guard'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Enum.valueOf: clase fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: Java 25 y nativo coinciden con array $VALUES mutado antes/después de primera consulta; directorio conserva instantánea y values alterado aborta')
