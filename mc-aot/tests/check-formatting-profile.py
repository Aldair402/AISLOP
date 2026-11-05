#!/usr/bin/env python3
"""Gson FormattingStyle: regex verificados y requireNonNull con mensaje."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src=r'''package net.minecraft.test;import java.util.Objects;public class FormatDemo {
 public static int run(int n){try{switch(n%9){case 0:return "\r\n\n".matches("[\\r\\n]*")?1:0;case 1:return "".matches("[\\r\\n]*")?2:0;case 2:return "x\n".matches("[\\r\\n]*")?0:3;case 3:return " \t\t".matches("[ \\t]*")?4:0;case 4:return "\n".matches("[ \\t]*")?0:5;case 5:return Objects.requireNonNull("x","oops").length();case 6:Objects.requireNonNull(null,"oops");return -1;case 7:Objects.requireNonNull(null);return -1;default:return "😀".matches("[ \\t]*")?0:9;}}catch(NullPointerException e){return e.getMessage()==null?70:e.getMessage().length()+70;}}
 public static int bad(){return "x".matches(".*")?1:0;}
}'''
driver='''import net.minecraft.test.FormatDemo;public class FormatDriver{public static void main(String[]a){for(String x:a)System.out.println(FormatDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-formatting-') as t:
 d=pathlib.Path(t);(d/'FormatDemo.java').write_text(src);(d/'FormatDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FormatDemo.java'),str(d/'FormatDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FormatDemo'];p=subprocess.run(base+[str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(90));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'FormatDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'regex fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 90 resultados Java regex de formato y mensajes requireNonNull; otros patrones abortan')
