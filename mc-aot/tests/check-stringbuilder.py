#!/usr/bin/env python3
"""StringBuilder acotado, snapshots, alias y cadenas UTF-16."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class BuilderDemo {
 static StringBuilder b=new StringBuilder();static String snap;
 public static int run(int n){try{switch(n){
 case 0:return b.toString()==""?1:0;
 case 1:return b.append("á").append((char)0xd800).append("!")==b?b.length():-1;
 case 2:snap=b.toString();return snap.length()*100+snap.charAt(1);
 case 3:b.append((String)null).append(false).append(true).append(-42).append(-9223372036854775807L);return b.length();
 case 4:return snap.length()==3&&snap.charAt(1)==0xd800?4:0;
 case 5:StringBuilder x=new StringBuilder("hola");String old=x.toString();x.append('!');return old.equals("hola")&&x.toString().equals("hola!")&&old!=x.toString()?5:0;
 case 6:StringBuilder y=new StringBuilder((String)null);return y.length();
 case 7:StringBuilder z=null;return z.append("x").length();
 case 8:StringBuilder q=new StringBuilder();return q.append(0).append(-2147483648).append(9223372036854775807L).toString().equals("0-21474836489223372036854775807")?8:0;
 case 9:StringBuilder t=new StringBuilder();return t.append((Object)"ok").append((Object)null).toString().equals("oknull")?9:0;
 case 10:new StringBuilder().append((Object)new Object());return -1;
 default:return 99;
 }}catch(NullPointerException e){return 101;}}
}'''
driver='''import net.minecraft.test.BuilderDemo;public class BuilderDriver{public static void main(String[] a){for(String s:a)System.out.println(BuilderDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-builder-') as t:
 d=pathlib.Path(t);(d/'BuilderDemo.java').write_text(source);(d/'BuilderDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'BuilderDemo.java'),str(d/'BuilderDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/BuilderDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in [0,1,2,3,4,5,6,7,8,9]*10+[-1,11]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'BuilderDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','10'],capture_output=True,text=True)
 if p.returncode!=2 or 'toString de objeto no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} operaciones Java StringBuilder: append, mutación, snapshots, UTF-16, null y extremos numéricos')
