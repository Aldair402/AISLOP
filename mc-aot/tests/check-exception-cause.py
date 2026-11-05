#!/usr/bin/env python3
"""Constructor IllegalStateException(String,Throwable), identidad de causa y mensaje."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class CauseDemo {public static int run(int n){Throwable c=new IllegalArgumentException("cause");IllegalStateException e=new IllegalStateException(n==0?null:"outer",n==1?null:c);try{throw e;}catch(IllegalStateException x){return (x==e?1:0)+(x.getCause()==c?2:0)+(x.getCause()==null?4:0)+(x.getMessage()==null?8:0)+(x.getMessage()!=null&&x.getMessage().equals("outer")?16:0);}}}'''
driver='''import net.minecraft.test.CauseDemo;public class CauseDriver{public static void main(String[]a){for(String s:a)System.out.println(CauseDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-cause-') as t:
 d=pathlib.Path(t);(d/'CauseDemo.java').write_text(source);(d/'CauseDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CauseDemo.java'),str(d/'CauseDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CauseDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=['0','1','2']*30;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'CauseDriver',*seq],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in seq for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(seq)} resultados Java para IllegalStateException con mensaje y causa, null e identidad')
