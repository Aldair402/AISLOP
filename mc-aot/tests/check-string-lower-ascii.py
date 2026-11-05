#!/usr/bin/env python3
"""String.toLowerCase: ASCII y caso I dependiente de locale explícita."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class LowerDemo{public static String run(String s){return s.toLowerCase();}public static int same(String s){return s.toLowerCase()==s?1:0;}}'''
driver='''import net.minecraft.test.LowerDemo;public class LowerDriver{public static void main(String[]a){for(String s:a){System.out.println(LowerDemo.run(s));System.out.println(LowerDemo.same(s));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-lower-') as t:
 d=pathlib.Path(t);(d/'LowerDemo.java').write_text(source);(d/'LowerDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LowerDemo.java'),str(d/'LowerDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LowerDemo',str(d/'native'),'run','(Ljava/lang/String;)Ljava/lang/String;','same','(Ljava/lang/String;)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['TRUE','false','IDENTITY','I','MiXeD','','lower 123']*5
 for language in ('en','tr','az'):
  java=subprocess.run([str(jdk/'java'),'-Duser.language='+language,'-cp',str(d),'LowerDriver',*vals],capture_output=True,text=True,check=True).stdout
  native=subprocess.run([str(d/'native'),*[v for s in vals for v in ('0','s:'+s,'1','s:'+s)]],capture_output=True,text=True,check=True,env=dict(os.environ,MC_AOT_JAVA_LANGUAGE=language)).stdout
  if java!=native:raise AssertionError((language,java,native))
 for s,expected in [('I','define MC_AOT_JAVA_LANGUAGE'),('Á','Unicode no soportado')]:
  env=dict(os.environ);env.pop('MC_AOT_JAVA_LANGUAGE',None);p=subprocess.run([str(d/'native'),'0','s:'+s],capture_output=True,text=True,env=env)
  if p.returncode!=2 or expected not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 210 resultados Java de lower ASCII con idiomas en/tr/az e identidad; casos sin perfil o Unicode abortan')
