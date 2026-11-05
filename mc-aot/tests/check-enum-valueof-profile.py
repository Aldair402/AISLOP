#!/usr/bin/env python3
"""Enum.valueOf acotado con values() canónico; no modela cualquier enum."""
import os,pathlib,subprocess,tempfile,sys
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'FixtureMode.java':'package net.minecraft.test;public enum FixtureMode{ALPHA,BETA,\u00c1RBOL}',
'EmptyMode.java':'package net.minecraft.test;public enum EmptyMode{}',
'FailMode.java':'package net.minecraft.test; public enum FailMode { A; static { if(fail()) throw new RuntimeException(); } static boolean fail(){return true;} }',
'ReentrantMode.java':'package net.minecraft.test; public enum ReentrantMode { A; ReentrantMode(){Enum.valueOf(ReentrantMode.class, "A");} }',
'InitDriver.java':'import net.minecraft.test.EnumValueProbe;public class InitDriver{public static void main(String[]a){System.out.println(EnumValueProbe.failingInit(0));System.out.println(EnumValueProbe.failingInit(1));}}',
'EnumValueProbe.java':'''package net.minecraft.test;
public class EnumValueProbe {
 enum Nested { A{int code(){return 12;}}, B{int code(){return 34;}}; abstract int code(); }
 public static int run(int n){try{switch(n%12){
 case 0:return Enum.valueOf(FixtureMode.class,"ALPHA")==FixtureMode.ALPHA?10:0;
 case 1:return FixtureMode.valueOf(new StringBuilder().append("BETA").toString()).ordinal();
 case 2:try{Enum.valueOf(FixtureMode.class,null);return -1;}catch(NullPointerException e){return "Name is null".equals(e.getMessage())?22:-22;}
 case 3:try{Enum.valueOf(FixtureMode.class,"missing");return -1;}catch(IllegalArgumentException e){return "No enum constant net.minecraft.test.FixtureMode.missing".equals(e.getMessage())?33:-33;}
 case 4:try{Enum.valueOf(FixtureMode.class,"");return -1;}catch(IllegalArgumentException e){return "No enum constant net.minecraft.test.FixtureMode.".equals(e.getMessage())?44:-44;}
 case 5:return Enum.valueOf(FixtureMode.class,"ÁRBOL")==FixtureMode.ÁRBOL?55:-55;
 case 6:return Enum.valueOf(Nested.class,"B").code();
 case 7:try{Enum.valueOf(null,"A");return -1;}catch(NullPointerException e){return 77;}
 case 8:try{Enum.valueOf(EmptyMode.class,"X");return -1;}catch(IllegalArgumentException e){return "No enum constant net.minecraft.test.EmptyMode.X".equals(e.getMessage())?88:-88;}
 case 9:FixtureMode[] v=FixtureMode.values();v[0]=null;return Enum.valueOf(FixtureMode.class,"ALPHA")==FixtureMode.ALPHA?99:-99;
 case 10:return FixtureMode.valueOf("BETA")==Enum.valueOf(FixtureMode.class,"BETA")?100:-100;
 default:try{Enum.valueOf(FixtureMode.class,"beta");return -1;}catch(IllegalArgumentException e){return 111;}
 }}catch(RuntimeException e){return -900;}}
 public static int failingInit(int n){try{Enum.valueOf(FailMode.class,null);return -1;}catch(ExceptionInInitializerError e){return 123;}catch(NoClassDefFoundError e){return 456;}}
 public static int reentrant(int n){Enum.valueOf(ReentrantMode.class,"A");return n;}
 public static int nestedMissing(int n){Enum.valueOf(Nested.class,"missing");return n;}
 @SuppressWarnings({"rawtypes","unchecked"}) public static int nonEnum(int n){Enum.valueOf((Class)String.class,"X");return n;}
 public static int javaEnum(int n){Enum.valueOf(java.util.concurrent.TimeUnit.class,"SECONDS");return n;}
}''',
'Driver.java':'import net.minecraft.test.EnumValueProbe;public class Driver{public static void main(String[]a){for(String x:a)System.out.println(EnumValueProbe.run(Integer.parseInt(x)));}}'
}
with tempfile.TemporaryDirectory(prefix='mc-enum-valueof-') as t:
 d=pathlib.Path(t);files=[]
 for name,src in sources.items():p=d/name;p.write_text(src);files.append(str(p))
 subprocess.run([str(jdk/'javac'),'-d',str(d),*files],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method,jar='fixture.jar'):
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/jar),'net/minecraft/test/EnumValueProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=180)
 for method in ('run','nestedMissing','nonEnum','failingInit','reentrant'):
  p=compile(method)
  if p.returncode:raise RuntimeError((method,p.stderr))
 vals=list(range(144));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
 p=subprocess.run([str(d/'run'),*[v for x in vals for v in ('0',str(x))]],capture_output=True,text=True)
 if p.returncode or p.stdout!=j:raise AssertionError((p.returncode,[(i,a,b) for i,(a,b) in enumerate(zip(j.splitlines(),p.stdout.splitlines())) if a!=b][:10],p.stderr))
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'InitDriver'],capture_output=True,text=True,check=True).stdout
 p=subprocess.run([str(d/'failingInit'),'0','0','0','1'],capture_output=True,text=True)
 if j!='123\n456\n' or p.returncode or p.stdout!=j:raise AssertionError(('initialization',j,p.returncode,p.stdout,p.stderr))
 for method,want in [('reentrant','Enum.valueOf: values aún no disponible'),('nestedMissing','nombre canónico anidado no modelado'),('nonEnum','Enum.valueOf: clase fuera del perfil')]:
  p=subprocess.run([str(d/method),'0','0'],capture_output=True,text=True)
  if p.returncode==0 or want not in p.stderr:raise AssertionError((method,p.returncode,p.stderr))
 p=compile('javaEnum')
 if p.returncode==0 or 'literal Class no soportado: java/util/concurrent/TimeUnit' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 144 resultados Enum.valueOf con Java 25; identidad, unicode, enum con subclase, null, errores e inicialización fallida; reentrada, anidado desconocido y clases no registradas abortan')
