#!/usr/bin/env python3
"""Campos reales int[] y char[] inicializados y reasignados por Minecraft."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3-inner.jar'
driver='''import java.lang.reflect.*;import java.util.Arrays;
public class StaticArraysReference {
 static String ints(int[] a){return a==null?"null":Arrays.toString(a).replace(" ","");}
 static String chars(char[] a){if(a==null)return "null";StringBuilder s=new StringBuilder("[");for(int i=0;i<a.length;i++){if(i>0)s.append(',');s.append((int)a[i]);}return s.append(']').toString();}
 public static void main(String[] args)throws Exception {
  Class<?> c=Class.forName(args[0]);Field f=c.getDeclaredField(args[1]);f.setAccessible(true);
  if(args[1].equals("HEX_CHAR")){System.out.println(chars((char[])f.get(null)));return;}
  Method init=c.getDeclaredMethod("init",int[].class);init.setAccessible(true);
  System.out.println(ints((int[])f.get(null)));
  for(int[] a:new int[][]{{1,-2,Integer.MAX_VALUE,Integer.MIN_VALUE},null,{}}){init.invoke(null,(Object)a);System.out.println("OK");System.out.println(ints((int[])f.get(null)));}
 }
}'''
with tempfile.TemporaryDirectory(prefix='mc-static-arrays-') as t:
 d=pathlib.Path(t);(d/'StaticArraysReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StaticArraysReference.java')],check=True)
 for label,cls,field in [('foliage','net/minecraft/world/level/FoliageColor','pixels'),('dry','net/minecraft/world/level/DryFoliageColor','pixels'),('hex','net/minecraft/server/rcon/PktUtils','HEX_CHAR')]:
  cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','multi-static-demo',str(jar),cls,str(d/label),'@'+field,('[C' if label=='hex' else '[I')]
  if label!='hex':cmd+=['init','([I)V']
  p=subprocess.run(cmd,capture_output=True,text=True)
  if p.returncode:raise RuntimeError((label,p.stderr))
  java=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),str(jar)]),'StaticArraysReference',cls.replace('/','.'),field],capture_output=True,text=True,check=True).stdout
  args=['0'] if label=='hex' else ['0','1','[1,-2,2147483647,-2147483648]','0','1','null','0','1','[]','0']
  native=subprocess.run([str(d/label),*args],capture_output=True,text=True,check=True).stdout
  if native!=java:raise AssertionError((label,len(java),len(native),java[:150],native[:150]))
  if label=='hex' and native.strip()!='[48,49,50,51,52,53,54,55,56,57,97,98,99,100,101,102]':raise AssertionError(native)
 print('OK: inicialización real de PktUtils.HEX_CHAR y dos arrays de 65,536 elementos; asignación de int[], null y vacío coinciden con Java 25')
