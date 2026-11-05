#!/usr/bin/env python3
"""version.json del classpath cerrado, InputStream básico y fallos explícitos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft;import java.io.*;public class DetectedVersion{
 public static int run(int n){try{InputStream in=DetectedVersion.class.getResourceAsStream("/version.json");if(in==null)return -7;switch(n%5){case 0:return in.read();case 1:in.read();return in.read();case 2:int sum=0,x;while((x=in.read())!=-1)sum+=x;return sum;case 3:in.close();return in.read();default:in.close();in.close();return 4;}}catch(IOException e){return 8;}}
 public static int other(){return DetectedVersion.class.getResourceAsStream("/other.txt")==null?1:0;}
}'''
driver='''import net.minecraft.DetectedVersion;public class ResourceDriver{public static void main(String[]a){for(String x:a)System.out.println(DetectedVersion.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-version-resource-') as t:
 d=pathlib.Path(t);(d/'DetectedVersion.java').write_text(src);(d/'ResourceDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DetectedVersion.java'),str(d/'ResourceDriver.java')],check=True)
 (d/'version.json').write_bytes(b'{"id":"26.3"}\n\x80\xff');subprocess.run([str(jdk/'jar'),'cf',str(d/'with.jar'),'-C',str(d),'net','-C',str(d),'version.json'],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'without.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo']; vals=list(range(50))
 for jar in ('with.jar','without.jar'):
  p=subprocess.run(base+[str(d/jar),'net/minecraft/DetectedVersion',str(d/'native'),'run','(I)I','other','()I'],capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
  j=subprocess.run([str(jdk/'java'),'-cp',str(d/jar)+':'+str(d),'ResourceDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
  # El directorio del driver no debe aportar version.json cuando el JAR carece de él.
  if jar=='without.jar':
   (d/'version.json').unlink();j=subprocess.run([str(jdk/'java'),'-cp',str(d/jar)+':'+str(d),'ResourceDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
  a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
  if j!=a:raise AssertionError((jar,j,a))
  p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
  if p.returncode==0 or 'fuera del perfil verificado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 100 operaciones Java con version.json presente/ausente, lectura, EOF y cierre; otros recursos abortan')
