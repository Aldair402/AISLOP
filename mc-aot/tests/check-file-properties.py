#!/usr/bin/env python3
"""Properties.load(InputStream), ISO-8859-1, continuaciones y fallos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src=r'''package net.minecraft.test;import java.nio.file.*;import java.io.*;import java.util.*;public class PropsFileDemo{public static int run(int n)throws Exception{Properties p=new Properties();try(InputStream f=Files.newInputStream(Path.of("prop"+(n%12)))){try{p.load(f);}catch(IllegalArgumentException e){return 900+p.getProperty("first","X").length();}}String v=p.getProperty("eula","fallback");int result=v.length()*100+(v.length()==0?0:v.charAt(0));if(Boolean.parseBoolean(v))result+=10000;String prior=(String)p.setProperty("eula","Z");return result+(prior==v?100000:0);}public static int missing(){try{Files.newInputStream(Path.of("no-file"));return 0;}catch(NoSuchFileException e){return e.getMessage().length();}catch(IOException e){return -1;}}}'''
driver='''import net.minecraft.test.PropsFileDemo;public class PDriver{public static void main(String[]a)throws Exception{for(String x:a)System.out.println(PropsFileDemo.run(Integer.parseInt(x)));System.out.println(PropsFileDemo.missing());}}'''
data=[b'eula=true\n',b' #comment\r\n eula : false\r\n',br'eula=\u0074rue'+b'\n',b'eula=tr\\\n   ue\n',b'eula=one\neula=true\n',br'eu\la\ =no'+b'\neula=a b\n',br'eula=\tX\n'+b'\n',b'eula=\xe9\n',b'eula\n',b'first=AA\neula=\\u0X00\n',b'eula=hello\\',b'eula=abc\\\n  \n']
with tempfile.TemporaryDirectory(prefix='mc-props-file-') as t:
 d=pathlib.Path(t);(d/'PropsFileDemo.java').write_text(src);(d/'PDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'PropsFileDemo.java'),str(d/'PDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PropsFileDemo',str(d/'native'),'run','(I)I','missing','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 for i,content in enumerate(data):(d/f'prop{i}').write_bytes(content)
 vals=list(range(120));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'PDriver',*map(str,vals)],cwd=d,capture_output=True,text=True,check=True);a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))],'1'],cwd=d,capture_output=True,text=True)
 if a.returncode or j.stdout!=a.stdout:raise AssertionError((a.returncode,j.stdout,a.stdout,a.stderr))
 print('OK: 120 lecturas de Properties.load y excepciones de archivo comparadas con Java')
