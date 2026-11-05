#!/usr/bin/env python3
"""Oracle Java de Eula al fallar tanto lectura como escritura; NO valida el adaptador."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];workspace=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-eula-thrown-') as t:
 d=pathlib.Path(t);libs=[]
 with zipfile.ZipFile(workspace/'downloads/server-26.3.jar') as z:
  for i,line in enumerate(z.read('META-INF/libraries.list').decode().splitlines()):
   sha,_,path=line.split('\t');b=z.read('META-INF/libraries/'+path)
   if hashlib.sha256(b).hexdigest()!=sha:raise AssertionError(path+' checksum')
   p=d/f'{i}.jar';p.write_bytes(b);libs.append(p)
 cp=os.pathsep.join([str(workspace/'downloads/server-26.3-inner.jar'),*[str(p) for p in libs]])
 subprocess.run([str(jdk/'javac'),'-cp',cp,'-d',str(d),str(root/'tests/EulaThrowableOracle.java')],check=True)
 (d/'log4j2.xml').write_text('<Configuration status="OFF"><Appenders/><Loggers><Root level="off"/></Loggers></Configuration>');(d/'eula.txt').mkdir()
 p=subprocess.run([str(jdk/'java'),'-Dlog4j2.configurationFile='+str(d/'log4j2.xml'),'-cp',str(d)+os.pathsep+cp,'EulaThrowableOracle'],cwd=d,capture_output=True,text=True,check=True,timeout=60)
 expected=['WARN|net.minecraft.server.Eula|Failed to load eula.txt|NO_THROWABLE','WARN|net.minecraft.server.Eula|Failed to save eula.txt|java.nio.file.FileSystemException']
 if p.stdout!='false\n' or p.stderr.splitlines()!=expected:raise AssertionError((p.stdout,p.stderr,expected))
 print('OK Java real: directorio eula.txt produce WARN de lectura sin Throwable y WARN de escritura con FileSystemException; log4rs aún no modela Throwable')
