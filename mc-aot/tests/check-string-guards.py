#!/usr/bin/env python3
"""Comprueba casts restringidos y orden de errores en aastore contra Java."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
fixture='''package net.minecraft.test;
public class StringGuards {
 public static int castText(String a){return ((String)(Object)a).length();}
 public static int castArray(int[] a){return ((String)(Object)a).length();}
 public static int castStrings(String[] a){return ((String[])(Object)a).length;}
 public static int storeSelf(String[] a){Object[] x=a;x[0]=x;return 1;}
}'''
driver='''import net.minecraft.test.StringGuards;
public class GuardsReference { public static void main(String[] a){try{int x=switch(a[0]){
 case "text" -> StringGuards.castText(a[1].equals("null")?null:a[1]);
 case "array" -> StringGuards.castArray(a[1].equals("null")?null:new int[1]);
 case "strings" -> StringGuards.castStrings(a[1].equals("null")?null:new String[1]);
 case "store" -> StringGuards.storeSelf(a[1].equals("null")?null:new String[Integer.parseInt(a[1])]);
 default -> throw new RuntimeException();};System.out.println(x);}catch(Throwable e){System.out.println("EX:"+e.getClass().getSimpleName());}}}'''
with tempfile.TemporaryDirectory(prefix='mc-string-guards-') as t:
 d=pathlib.Path(t);(d/'StringGuards.java').write_text(fixture);(d/'GuardsReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StringGuards.java'),str(d/'GuardsReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 specs={'text':('castText','(Ljava/lang/String;)I'),'array':('castArray','([I)I'),'strings':('castStrings','([Ljava/lang/String;)I'),'store':('storeSelf','([Ljava/lang/String;)I')}
 for label,(name,desc) in specs.items():
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'test.jar'),'net/minecraft/test/StringGuards',name,desc,str(d/label)],capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
 cases=[('text','hola','s:hola'),('text','null','null'),('array','x','[1]'),('array','null','null'),('strings','x','sarr:[n]'),('strings','null','null'),('store','null','null'),('store','0','sarr:[]'),('store','1','sarr:[n]')]
 for op,jarg,narg in cases:
  expected=subprocess.run([str(jdk/'java'),'-cp',str(d),'GuardsReference',op,jarg],capture_output=True,text=True,check=True).stdout.strip()
  got=subprocess.run([str(d/op),narg],capture_output=True,text=True)
  if expected.startswith('EX:'):
   if got.returncode==0 or expected[3:] not in got.stderr:raise AssertionError((op,jarg,expected,got.stdout,got.stderr))
  elif got.returncode or got.stdout.strip()!=expected:raise AssertionError((op,jarg,expected,got.stdout,got.stderr))
 print(f'OK: {len(cases)} casts y errores de aastore coinciden con Java por valor o categoría; fallos no capturados terminan el proceso')
