#!/usr/bin/env python3
"""Perfil de datos RuntimePermission(String), no aplica políticas de seguridad."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.security.Permission;
public class PermissionProbe {
 public static int run(int n){try{
  String s;switch(n%8){case 0:s=null;break;case 1:s="";break;case 2:s="getClassLoader";break;case 3:s="*";break;case 4:s="some.*";break;case 5:s="💎.名称";break;case 6:s="\\u0000";break;default:s=" ";}
  RuntimePermission p=new RuntimePermission(s);Permission q=p;
  return (p.getName()==s?1:0)+(q.getName()==s?2:0)+(p.getActions().equals("")?4:0)+(q.getActions().equals("")?8:0)+(p.getClass()==RuntimePermission.class?16:0)+(p.getClass().getClassLoader()==null?32:0);
 }catch(NullPointerException e){return 100;}catch(IllegalArgumentException e){return e.getMessage().equals("name can't be empty")?101:102;}}
 public static int unsupported(int n){return new RuntimePermission("getClassLoader").implies(new RuntimePermission("getClassLoader"))?1:0;}
}'''
driver='''import net.minecraft.test.PermissionProbe;public class PermissionDriver{public static void main(String[]a){for(String n:a)System.out.println(PermissionProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-permission-') as temp:
 d=pathlib.Path(temp);(d/'PermissionProbe.java').write_text(source);(d/'PermissionDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'PermissionProbe.java'),str(d/'PermissionDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PermissionProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'PermissionDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('unsupported')
 if p.returncode==0 or 'implies' not in p.stderr:raise AssertionError(('implies guard',p.stderr))
 print(f'OK: {len(vals)} resultados RuntimePermission(String), nombre, acciones, identidad, class y excepciones; implies se rechaza; sin políticas de seguridad')
