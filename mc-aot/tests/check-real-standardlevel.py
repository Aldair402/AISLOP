#!/usr/bin/env python3
"""StandardLevel real, EnumSet.allOf y selección ordinal en Log4j."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';bundle=root.parent/'downloads/server-26.3.jar'
src='''package net.minecraft.test;import org.apache.logging.log4j.spi.StandardLevel;public class Log4jLevelDemo{public static int run(int n){StandardLevel l=StandardLevel.getStandardLevel(n);return l.ordinal()*10000+l.intLevel();}}'''
driver='''import net.minecraft.test.Log4jLevelDemo;public class LevelDriver{public static void main(String[]a){for(String x:a)System.out.println(Log4jLevelDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-standard-level-') as t:
 d=pathlib.Path(t)
 with zipfile.ZipFile(bundle) as z:
  names=[n for n in z.namelist() if '/log4j-api/' in n and n.endswith('.jar')];assert len(names)==1;api=z.read(names[0])
 (d/'log4j.jar').write_bytes(api);(d/'Log4jLevelDemo.java').write_text(src);(d/'LevelDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-cp',str(d/'log4j.jar'),'-d',str(d),str(d/'Log4jLevelDemo.java'),str(d/'LevelDriver.java')],check=True)
 with zipfile.ZipFile(d/'log4j.jar') as z:
  name='org/apache/logging/log4j/spi/StandardLevel.class';p=d/name;p.parent.mkdir(parents=True);p.write_bytes(z.read(name))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'org'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Log4jLevelDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-300,1200,7))+[2147483647,-2147483648];j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(d/'log4j.jar'),'LevelDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print(f'OK: {len(vals)} consultas al StandardLevel real y EnumSet.allOf limitado')
