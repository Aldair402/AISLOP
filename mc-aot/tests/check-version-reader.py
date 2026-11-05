#!/usr/bin/env python3
"""InputStreamReader UTF-8 válido sobre version.json cerrado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft;import java.io.*;import java.nio.charset.StandardCharsets;public class DetectedVersion {
 public static int run(int n){try{InputStream in=DetectedVersion.class.getResourceAsStream("/version.json");Reader r=new InputStreamReader(in,StandardCharsets.UTF_8);switch(n%11){case 0:return r.read();case 1:r.read();return r.read();case 2:r.read();r.read();return r.read();case 3:char[] c=new char[8];int count=r.read(c,1,6);return count*100000+c[3];case 4:r.close();return r.read();case 5:char[] x=new char[1];return r.read(x,0,0);case 6:char[] y=new char[1];r.read(y,0,0);return in.read();case 7:r.close();return r.read(null,0,0);case 8:r.close();return r.read(new char[0],-1,0);case 9:r.close();return r.read(new char[0],0,0);default:int sum=0,v;while((v=r.read())!=-1)sum+=v;return sum;}}catch(IOException e){return 77;}}
}'''
driver='''import net.minecraft.DetectedVersion;public class ResourceDriver{public static void main(String[]a){for(String x:a)System.out.println(DetectedVersion.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-version-reader-') as t:
 d=pathlib.Path(t);(d/'DetectedVersion.java').write_text(src);(d/'ResourceDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DetectedVersion.java'),str(d/'ResourceDriver.java')],check=True);(d/'version.json').write_text('aé😀Z\n',encoding='utf8');subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'version.json'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/DetectedVersion',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(110));j=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+':'+str(d),'ResourceDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 print('OK: 110 operaciones Reader UTF-8 válido, char[], pares sustitutos, EOF y cierre')
