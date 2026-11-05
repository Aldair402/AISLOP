#!/usr/bin/env python3
"""Constructores delegantes reales de JsonParseException del bundle oficial."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';bundle=root.parent/'downloads/server-26.3.jar'
src='''package net.minecraft.test;import com.google.gson.JsonParseException;import java.io.IOException;public class GsonExceptionDemo{public static int run(int n){try{if(n%4==0)throw new JsonParseException("foo");if(n%4==1)throw new JsonParseException(new IOException("closed"));if(n%4==2)throw new JsonParseException("bar",new IOException("inner"));throw new JsonParseException((Throwable)null);}catch(JsonParseException e){String m=e.getMessage();int score=m==null?0:m.length();return score+(e.getCause()==null?0:100);} }}'''
driver='''import net.minecraft.test.GsonExceptionDemo;public class GsonDriver{public static void main(String[]a){for(String x:a)System.out.println(GsonExceptionDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-gson-exception-') as t:
 d=pathlib.Path(t)
 with zipfile.ZipFile(bundle) as z:
  names=[n for n in z.namelist() if '/gson/' in n and n.endswith('.jar')];assert len(names)==1;gson=z.read(names[0])
 (d/'gson.jar').write_bytes(gson);(d/'GsonExceptionDemo.java').write_text(src);(d/'GsonDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-cp',str(d/'gson.jar'),'-d',str(d),str(d/'GsonExceptionDemo.java'),str(d/'GsonDriver.java')],check=True)
 with zipfile.ZipFile(d/'gson.jar') as z:
  p=d/'com/google/gson/JsonParseException.class';p.parent.mkdir(parents=True);p.write_bytes(z.read('com/google/gson/JsonParseException.class'))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'com'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/GsonExceptionDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(d/'gson.jar'),'GsonDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 80 operaciones de JsonParseException real con mensaje y causa')
