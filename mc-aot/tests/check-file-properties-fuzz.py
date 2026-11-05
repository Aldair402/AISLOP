#!/usr/bin/env python3
"""Fuzz determinista del parser Properties.load contra Java 25."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src=r'''package net.minecraft.test;import java.nio.file.*;import java.io.*;import java.util.*;public class PropsFuzz{public static int run(int n)throws IOException{Properties p=new Properties();int err=0;try(InputStream f=Files.newInputStream(Path.of("prop"+n))){try{p.load(f);}catch(IllegalArgumentException e){err=1;}}int h=err;for(String k:new String[]{"a","b","eula","first","a b","", "#x"}){String v=p.getProperty(k);h=h*31+(v==null?1234567:v.hashCode());}return h;}}'''
driver='''import net.minecraft.test.PropsFuzz;public class PFDriver{public static void main(String[]a)throws Exception{for(String x:a)System.out.println(PropsFuzz.run(Integer.parseInt(x)));}}'''
rng=random.Random(49201);keys=[b'a',b'b',b'eula',b'first',br'a\ b',b'',br'\#x',b'junk'];values=[b'',b'true',b'  ',br'\tX',br'\u00e9',br'\uD83D\uDE80',br'\u00xx',br'yes\ no',b'x\\\n y',b'foo\\\r\n#z',b'abc\\',b'\\\\',bytes([0xe9,0xff])];seps=[b'=',b':',b' = ',b'\t',b'   :'];eols=[b'\n',b'\r',b'\r\n']
with tempfile.TemporaryDirectory(prefix='mc-props-fuzz-') as t:
 d=pathlib.Path(t);(d/'PropsFuzz.java').write_text(src);(d/'PFDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'PropsFuzz.java'),str(d/'PFDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/PropsFuzz',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 for i in range(200):
  lines=[]
  for _ in range(rng.randrange(1,8)):
   if rng.randrange(8)==0:line=rng.choice([b' # comment',b'!comment',b'  '])
   else:line=rng.choice([b'',b' ',b'\t'])+rng.choice(keys)+rng.choice(seps)+rng.choice(values)
   lines.append(line+rng.choice(eols))
  if rng.randrange(3)==0:lines[-1]=lines[-1].rstrip(b'\r\n')
  (d/f'prop{i}').write_bytes(b''.join(lines))
 vals=list(range(200));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'PFDriver',*map(str,vals)],cwd=d,capture_output=True,text=True,check=True);a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],cwd=d,capture_output=True,text=True)
 if a.returncode:raise AssertionError((a.returncode,a.stderr))
 jv=j.stdout.splitlines();av=a.stdout.splitlines();bad=[i for i in vals if jv[i]!=av[i]]
 if bad:
  i=bad[0];raise AssertionError((bad[:20],i,(d/f'prop{i}').read_bytes(),jv[i],av[i]))
 print('OK: 200 archivos aleatorios y 1400 consultas Properties.load comparadas con Java')
