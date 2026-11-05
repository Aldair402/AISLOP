#!/usr/bin/env python3
"""jopt-simple AbbreviationMap real, insert, prefijos, borrado y orden TreeMap."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';bundle=root.parent/'downloads/server-26.3.jar'
src='''package net.minecraft.test;import joptsimple.internal.AbbreviationMap;import java.util.*;public class AbbrevDemo{public static int run(int n){AbbreviationMap<String> m=new AbbreviationMap<>();m.put("alpha","A");m.put("alpine","B");m.put("beta","C");switch(n%7){case 0:return m.get("alpha").length();case 1:return m.get("al")==null?2:0;case 2:return m.get("bet").length();case 3:m.remove("alpine");return m.get("al").length();case 4:m.remove("beta");return m.contains("beta")?0:4;case 5:return m.toJavaUtilMap().size();default:Map<String,String> t=m.toJavaUtilMap();return t.values().iterator().next().charAt(0);}}}'''
driver='''import net.minecraft.test.AbbrevDemo;public class AbbrevDriver{public static void main(String[]a){for(String x:a)System.out.println(AbbrevDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-jopt-abbrev-') as t:
 d=pathlib.Path(t)
 with zipfile.ZipFile(bundle) as z:
  names=[n for n in z.namelist() if '/jopt-simple/' in n and n.endswith('.jar')];assert len(names)==1;jopt=z.read(names[0])
 (d/'jopt.jar').write_bytes(jopt);(d/'AbbrevDemo.java').write_text(src);(d/'AbbrevDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-cp',str(d/'jopt.jar'),'-d',str(d),str(d/'AbbrevDemo.java'),str(d/'AbbrevDriver.java')],check=True)
 with zipfile.ZipFile(d/'jopt.jar') as z:
  for name in ('joptsimple/internal/AbbreviationMap.class','joptsimple/internal/OptionNameMap.class'):
   p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'joptsimple'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/AbbrevDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(140));j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(d/'jopt.jar'),'AbbrevDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 140 operaciones del AbbreviationMap real de jopt-simple y TreeMap ordenado')
