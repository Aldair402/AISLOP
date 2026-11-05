#!/usr/bin/env python3
"""Propiedades restringidas, configuradas explícitamente; no representa todas las propiedades de JVM."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class PropertiesDemo {
 static String saved;
 public static String get(String k){return System.getProperty(k);}
 public static String fallback(String k,String v){return System.getProperty(k,v);}
 public static String put(String k,String v){return System.setProperty(k,v);}
 public static String clear(String k){return System.clearProperty(k);}
 public static void save(String k){saved=System.getProperty(k);}
 public static int same(String k){return saved==System.getProperty(k)?1:0;}
}'''
driver='''import net.minecraft.test.PropertiesDemo;
public class PropertiesDriver {public static void main(String[] a){System.out.println(PropertiesDemo.get("slf4j.fixture"));System.out.println(PropertiesDemo.fallback("slf4j.absent","fallback"));PropertiesDemo.save("slf4j.fixture");System.out.println("OK");System.out.println(PropertiesDemo.same("slf4j.fixture"));System.out.println(PropertiesDemo.put("slf4j.fixture","new"));System.out.println(PropertiesDemo.get("slf4j.fixture"));System.out.println(PropertiesDemo.same("slf4j.fixture"));System.out.println(PropertiesDemo.put("slf4j.empty",""));System.out.println(PropertiesDemo.get("slf4j.empty"));System.out.println(PropertiesDemo.clear("slf4j.fixture"));System.out.println(PropertiesDemo.get("slf4j.fixture"));System.out.println(PropertiesDemo.get("max.bg.threads"));}}'''
with tempfile.TemporaryDirectory(prefix='mc-properties-') as t:
 d=pathlib.Path(t);(d/'PropertiesDemo.java').write_text(source);(d/'PropertiesDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'PropertiesDemo.java'),str(d/'PropertiesDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('get','(Ljava/lang/String;)Ljava/lang/String;'),('fallback','(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'),('put','(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'),('clear','(Ljava/lang/String;)Ljava/lang/String;'),('save','(Ljava/lang/String;)V'),('same','(Ljava/lang/String;)I')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PropertiesDemo',str(d/'native')]
 for n,desc in specs:cmd += [n,desc]
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 env={**os.environ,'MC_AOT_JAVA_PROPERTIES':'slf4j.fixture=valor-🚀\nmax.bg.threads=5'}
 java=subprocess.run([str(jdk/'java'),'-Dslf4j.fixture=valor-🚀','-Dmax.bg.threads=5','-cp',str(d),'PropertiesDriver'],capture_output=True,text=True,check=True).stdout
 args=['0','s:slf4j.fixture','1','s:slf4j.absent','s:fallback','4','s:slf4j.fixture','5','s:slf4j.fixture','2','s:slf4j.fixture','s:new','0','s:slf4j.fixture','5','s:slf4j.fixture','2','s:slf4j.empty','s:','0','s:slf4j.empty','3','s:slf4j.fixture','0','s:slf4j.fixture','0','s:max.bg.threads']
 native=subprocess.run([str(d/'native'),*args],env=env,capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 for args,expected in [(['0','null'],'NullPointerException'),(['0','s:'],'IllegalArgumentException'),(['2','s:slf4j.x','null'],'NullPointerException'),(['0','s:java.version'],'propiedad JVM no soportada')]:
  p=subprocess.run([str(d/'native'),*args],env=env,capture_output=True,text=True)
  if p.returncode!=2 or expected not in p.stderr:raise AssertionError((args,p.returncode,p.stderr))
 print('OK: 12 operaciones Java de propiedades slf4j, identidad y configuración explícita; 4 guardas')
