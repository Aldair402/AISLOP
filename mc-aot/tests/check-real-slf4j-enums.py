#!/usr/bin/env python3
"""Contrasta dos enums reales del slf4j-api contenido en el servidor oficial."""
import os,pathlib,subprocess,tempfile,zipfile,io,hashlib
root=pathlib.Path(__file__).resolve().parents[1];workspace=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
stub='''package org.slf4j.helpers;public class Reporter {public enum Level {DEBUG,INFO,WARN,ERROR;int levelInt;}public enum TargetChoice{Stderr,Stdout;}}'''
probe='''package org.slf4j.helpers; public class EnumProbe {public static int run(int n){switch(n){case 0:return Reporter.Level.DEBUG.ordinal()+Reporter.Level.INFO.ordinal()*10+Reporter.Level.WARN.ordinal()*100+Reporter.Level.ERROR.ordinal()*1000;case 1:return Reporter.Level.INFO.name().equals("INFO")?1:0;case 2:return Reporter.Level.DEBUG.levelInt+Reporter.Level.INFO.levelInt+Reporter.Level.WARN.levelInt+Reporter.Level.ERROR.levelInt;case 3:return Reporter.Level.values().length*10+Reporter.TargetChoice.values().length;case 4:return Reporter.TargetChoice.Stderr.ordinal()*10+Reporter.TargetChoice.Stdout.ordinal();case 5:Reporter.Level[] a=Reporter.Level.values(),b=Reporter.Level.values();a[0]=Reporter.Level.ERROR;return a!=b&&b[0]==Reporter.Level.DEBUG?5:0;default:return 99;}}}'''
driver='''import org.slf4j.helpers.EnumProbe;public class EnumProbeDriver{public static void main(String[] a){for(String s:a)System.out.println(EnumProbe.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-real-enum-') as t:
 d=pathlib.Path(t);bundle=workspace/'downloads/server-26.3.jar'
 with zipfile.ZipFile(bundle) as z:
  line=next(l for l in z.read('META-INF/libraries.list').decode().splitlines() if '\torg.slf4j:slf4j-api:' in l);digest,_,path=line.split('\t');lib=z.read('META-INF/libraries/'+path)
 if hashlib.sha256(lib).hexdigest()!=digest:raise AssertionError('checksum slf4j incorrecto')
 (d/'Reporter.java').write_text(stub);(d/'EnumProbe.java').write_text(probe);(d/'EnumProbeDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'Reporter.java'),str(d/'EnumProbe.java'),str(d/'EnumProbeDriver.java')],check=True)
 for f in (d/'org/slf4j/helpers').glob('Reporter*.class'):f.unlink()
 (d/'slf4j.jar').write_bytes(lib)
 with zipfile.ZipFile(d/'fixture.jar','w') as z,zipfile.ZipFile(io.BytesIO(lib)) as original:
  z.write(d/'org/slf4j/helpers/EnumProbe.class','org/slf4j/helpers/EnumProbe.class')
  for name in ['org/slf4j/helpers/Reporter$Level.class','org/slf4j/helpers/Reporter$TargetChoice.class'] :z.writestr(name,original.read(name))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'org/slf4j/helpers/EnumProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(6))*15+[-1,6]];java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(d/'slf4j.jar'),'EnumProbeDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)} operaciones sobre los dos enums reales de Reporter de slf4j-api 2.0.17 del bundle (SHA-256 verificado); no certifica clases completas')
