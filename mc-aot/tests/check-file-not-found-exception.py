#!/usr/bin/env python3
"""Constructor y jerarquía FileNotFoundException, sin mapear más operaciones de E/S."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.io.*;public class FileNotFoundProbe{
 static void fail(int n)throws IOException {if(n%3==0)throw new FileNotFoundException();if(n%3==1)throw new FileNotFoundException("missing");throw new IOException("other");}
 public static int run(int n){try{fail(n);return -1;}catch(FileNotFoundException e){return (e.getMessage()==null?1:e.getMessage().equals("missing")?2:3)+(e.getClass().getName().equals("java.io.FileNotFoundException")?10:0)+(e instanceof IOException?100:0);}catch(IOException e){return e.getMessage().equals("other")?200:201;}}
}'''
driver='''import net.minecraft.test.FileNotFoundProbe;public class FileNotFoundDriver{public static void main(String[]a){for(String n:a)System.out.println(FileNotFoundProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-filenotfound-') as tmp:
 d=pathlib.Path(tmp);(d/'FileNotFoundProbe.java').write_text(source);(d/'FileNotFoundDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FileNotFoundProbe.java'),str(d/'FileNotFoundDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FileNotFoundProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-20,61));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'FileNotFoundDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 print(f'OK: {len(vals)} resultados FileNotFoundException, mensajes, getClass y catch IOException frente a Java')
