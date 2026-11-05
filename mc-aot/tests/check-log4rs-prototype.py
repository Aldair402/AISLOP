#!/usr/bin/env python3
"""Diferencial del sink log4rs aislado con SLF4J/Log4j oficiales del bundle."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1]; workspace=root.parent; jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-log4rs-oracle-') as t:
 d=pathlib.Path(t); libs=[]
 with zipfile.ZipFile(workspace/'downloads/server-26.3.jar') as z:
  for line in z.read('META-INF/libraries.list').decode().splitlines():
   sha,name,path=line.split('\t')
   if name.startswith(('org.slf4j:slf4j-api:','org.apache.logging.log4j:log4j-api:','org.apache.logging.log4j:log4j-core:','org.apache.logging.log4j:log4j-slf4j2-impl:')):
    b=z.read('META-INF/libraries/'+path)
    if hashlib.sha256(b).hexdigest()!=sha:raise AssertionError(name+' checksum')
    p=d/(pathlib.Path(path).name);p.write_bytes(b);libs.append(p)
 if len(libs)!=4:raise AssertionError(libs)
 cp=os.pathsep.join(map(str,libs))
 subprocess.run([str(jdk/'javac'),'-cp',cp,'-d',str(d),str(root/'tests/Log4rsOracle.java')],check=True)
 (d/'log4j2.xml').write_text('<Configuration status="OFF"><Appenders/><Loggers><Root level="off"/></Loggers></Configuration>')
 subprocess.run(['cargo','build','--quiet','--locked','--target-dir',str(root/'log4rs-prototype/target'),'--manifest-path',str(root/'log4rs-prototype/Cargo.toml')],check=True,timeout=240)
 binary=root/'log4rs-prototype/target/debug/mc-log4rs-prototype'
 count=0
 for level in ['OFF','ERROR','WARN','INFO','DEBUG','TRACE']:
  j=subprocess.run([str(jdk/'java'),'-Dlog4j2.configurationFile='+str(d/'log4j2.xml'),'-cp',str(d)+os.pathsep+cp,'Log4rsOracle',level],capture_output=True,text=True,cwd=d,check=True,timeout=60)
  file=d/(level+'.log');n=subprocess.run([str(binary),str(file),level],capture_output=True,text=True,check=True,timeout=60)
  if j.stdout!=n.stdout:raise AssertionError((level,'enabled',j.stdout,n.stdout))
  data=file.read_text();
  if j.stderr!=data:
   import itertools
   mismatch=next(((i,a,b) for i,(a,b) in enumerate(itertools.zip_longest(j.stderr.splitlines(),data.splitlines())) if a!=b),None)
   raise AssertionError((level,'events',mismatch,'java_lines',len(j.stderr.splitlines()),'native_lines',len(data.splitlines())))
  count+=len(data.splitlines())
 print(f'OK: {count} eventos reales y 120 consultas isEnabled con seis niveles de raíz frente a SLF4J+Log4j oficiales; archivo log4rs real; no es configuración Minecraft ni conexión al backend')
