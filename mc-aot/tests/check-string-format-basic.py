#!/usr/bin/env python3
"""Subconjunto explícito de Formatter: %s con String/null, %%, %n."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class FormatDemo {
 public static int run(int n){try{String s;switch(n){
 case 0:s=String.format("%s-%s%%!", "ABC",null);return s.equals("ABC-null%!")?10:0;
 case 1:s=String.format("hello");return s.equals("hello")&&s!="hello"?11:0;
 case 2:s=String.format("%s/%s",(Object[])null);return s.equals("null/null")?12:0;
 case 3:s=String.format("%s",new String[]{"x","extra"});return s.equals("x")?13:0;
 case 4:s=String.format("<%n>");return s.equals("<\\n>")?14:0;
 case 5:s=String.format("α%s終","á𝄞");return s.equals("αá𝄞終")?15:0;
 case 6:s=String.format((String)null,"x");return -1;
 case 7:s=String.format("%s",new Object());return -1;
 case 8:s=String.format("%d","x");return -1;
 case 9:s=String.format("%s");return -1;
 default:return 19;
 }}catch(NullPointerException e){return 16;}}
}'''
driver='''import net.minecraft.test.FormatDemo;public class FormatDriver{public static void main(String[] a){for(String s:a)System.out.println(FormatDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-format-') as t:
 d=pathlib.Path(t);(d/'FormatDemo.java').write_text(source);(d/'FormatDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FormatDemo.java'),str(d/'FormatDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FormatDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(7))*10+[-1,10]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'FormatDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 for x in ('7','8','9'):
  p=subprocess.run([str(d/'native'),'0',x],capture_output=True,text=True)
  if p.returncode!=2 or 'String.format:' not in p.stderr:raise AssertionError((x,p.stdout,p.stderr,p.returncode))
 print(f'OK: {len(vals)} formatos Java con String/null, %% y %n; tres formatos/argumentos fuera del subconjunto abortan explícitamente')
