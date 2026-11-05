#!/usr/bin/env python3
"""getDeclaredConstructor solo para clases registradas y constructor público ()V."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'DeclaredProbe.java':'''package net.minecraft.test;import java.lang.reflect.*;public class DeclaredProbe{public static int count;
 public static int run(int n){try{if((n&1)!=0){NoDefault.class.getDeclaredConstructor();return -1;}Constructor<?> c=PublicCtor.class.getDeclaredConstructor((Class<?>[])null);Object o=c.newInstance((Object[])null);return (o instanceof PublicCtor?10:0)+count;}catch(NoSuchMethodException e){return 20+count;}catch(ReflectiveOperationException e){return -2;}}
 public static int nonPublic(int n)throws Exception{return PrivateCtor.class.getDeclaredConstructor()==null?1:0;}
 public static int unregistered(int n)throws Exception{return String.class.getDeclaredConstructor()==null?1:0;}
}''',
'PublicCtor.java':'''package net.minecraft.test;public class PublicCtor{public PublicCtor(){DeclaredProbe.count++;}}''',
'NoDefault.java':'''package net.minecraft.test;public class NoDefault{public NoDefault(int n){}}''',
'PrivateCtor.java':'''package net.minecraft.test;public class PrivateCtor{private PrivateCtor(){}}''',
'DeclaredDriver.java':'''import net.minecraft.test.DeclaredProbe;public class DeclaredDriver{public static void main(String[]a){for(String n:a)System.out.println(DeclaredProbe.run(Integer.parseInt(n)));}}'''}
with tempfile.TemporaryDirectory(prefix='mc-declared-') as tmp:
 d=pathlib.Path(tmp)
 for n,t in sources.items():(d/n).write_text(t)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/n) for n in sources]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 env=dict(os.environ,MC_AOT_REFLECT_CLASSES=':'.join('net/minecraft/test/'+n for n in ('PublicCtor','NoDefault','PrivateCtor')))
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DeclaredProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,env=env,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DeclaredDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 for method,want in [('nonPublic','constructor no público fuera del perfil'),('unregistered','clase no registrada')]:
  p=compile(method)
  if p.returncode:raise RuntimeError(p.stderr)
  n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
  if n.returncode==0 or want not in n.stderr:raise AssertionError((method,n.stderr))
 print(f'OK: {len(vals)} resultados getDeclaredConstructor público/ausente frente a Java; rechaza privado y clase no registrada')
