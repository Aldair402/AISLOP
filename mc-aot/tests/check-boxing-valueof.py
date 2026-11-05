#!/usr/bin/env python3
"""Boxing Integer y String.valueOf en perfiles admitidos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class ValueOfDemo{public static int run(int n,int op){try{switch(op){case 0:Integer a=Integer.valueOf(n),b=Integer.valueOf(n);return a.intValue()==n?(a==b?1:2):0;case 1:return String.valueOf(n).equals(Integer.toString(n))?3:0;case 2:return String.valueOf(n!=0).equals(n!=0?"true":"false")?4:0;case 3:Object x="hi";return String.valueOf(x)==x?5:0;case 4:Object z=null;return String.valueOf(z)=="null"?6:0;case 5:Integer nil=null;return nil.intValue();case 6:Object o=Integer.valueOf(n);return o.getClass().getName().equals("java.lang.Integer")?7:0;case 7:Object bad=new Object();return String.valueOf(bad).length();default:return 99;}}catch(NullPointerException e){return 105;}}}'''
# Integer.toString sustituido por comparación interna para no requerir otra intrínseca.
source=source.replace('String.valueOf(n).equals(Integer.toString(n))','String.valueOf(n).equals(""+n)')
driver='''import net.minecraft.test.ValueOfDemo;public class ValueDriver{public static void main(String[]a){for(int i=0;i<a.length;i+=2)System.out.println(ValueOfDemo.run(Integer.parseInt(a[i]),Integer.parseInt(a[i+1])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-boxing-') as t:
 d=pathlib.Path(t);(d/'ValueOfDemo.java').write_text(source);(d/'ValueDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ValueOfDemo.java'),str(d/'ValueDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ValueOfDemo',str(d/'native'),'run','(II)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[(str(n),str(op)) for n in [-2147483648,-129,-128,-1,0,1,127,128,2147483647] for op in range(7)]*2;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ValueDriver',*[v for pair in vals for v in pair]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n,op in vals for v in ('0',n,op)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','1','7'],capture_output=True,text=True)
 if p.returncode!=2 or 'solo String/null soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} resultados Java de boxing, caché Integer, null y String.valueOf; objetos arbitrarios abortan')
