#!/usr/bin/env python3
"""ConcurrentHashMap.computeIfAbsent monohilo, con callback traducido."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.concurrent.*;import java.util.function.*;
public class ComputeDemo{
 static ConcurrentMap<String,String> m=new ConcurrentHashMap<>();static int calls;
 static String calc(String k){calls++;if(k.equals("null"))return null;if(k.equals("throw"))throw new IllegalArgumentException();return k.trim();}
 public static int run(int n){try{switch(n%10){case 0:return m.computeIfAbsent("  a  ",ComputeDemo::calc).length()*10+calls;case 1:return m.computeIfAbsent("  a  ",ComputeDemo::calc).length()*10+calls;case 2:return m.computeIfAbsent("null",ComputeDemo::calc)==null?calls:99;case 3:m.computeIfAbsent("throw",ComputeDemo::calc);return 0;case 4:return calls;case 5:m.computeIfAbsent(null,ComputeDemo::calc);return -1;case 6:m.computeIfAbsent("  a  ",null);return -1;case 7:m.remove("  a  ");return m.size();case 8:return m.computeIfAbsent(" b ", k->"xy").length();default:return m.size();}}catch(NullPointerException e){return 77;}catch(IllegalArgumentException e){return 88;}}
 public static int reentrant(){m.computeIfAbsent("a",k->{m.put("b","x");return "y";});return 0;}
}'''
driver='''import net.minecraft.test.ComputeDemo;public class ComputeDriver{public static void main(String[]a){for(String s:a)System.out.println(ComputeDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-map-compute-') as t:
 d=pathlib.Path(t);(d/'ComputeDemo.java').write_text(src);(d/'ComputeDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ComputeDemo.java'),str(d/'ComputeDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ComputeDemo']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I','reentrant','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(100));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'ComputeDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[x for n in vals for x in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'mutación reentrante no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 100 resultados computeIfAbsent, valores null, excepción, caché, NPE y guarda de mutación reentrante')
