#!/usr/bin/env python3
"""Evento Eula real Java vs fixture log4rs; NO traduce Eula ni su logger."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];workspace=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-eula-log-oracle-') as t:
 d=pathlib.Path(t);libs=[]
 with zipfile.ZipFile(workspace/'downloads/server-26.3.jar') as z:
  for i,line in enumerate(z.read('META-INF/libraries.list').decode().splitlines()):
   sha,_,path=line.split('\t');b=z.read('META-INF/libraries/'+path)
   if hashlib.sha256(b).hexdigest()!=sha:raise AssertionError(path+' checksum')
   p=d/f'{i}.jar';p.write_bytes(b);libs.append(p)
 cp=os.pathsep.join([str(workspace/'downloads/server-26.3-inner.jar'),*[str(p) for p in libs]])
 subprocess.run([str(jdk/'javac'),'-cp',cp,'-d',str(d),str(root/'tests/EulaLogOracle.java')],check=True)
 (d/'log4j2.xml').write_text('<Configuration status="OFF"><Appenders/><Loggers><Root level="off"/></Loggers></Configuration>')
 j=subprocess.run([str(jdk/'java'),'-Dlog4j2.configurationFile='+str(d/'log4j2.xml'),'-cp',str(d)+os.pathsep+cp,'EulaLogOracle'],cwd=d,capture_output=True,text=True,check=True,timeout=60)
 if j.stdout!='false\n' or not (d/'eula.txt').is_file() or 'eula=false' not in (d/'eula.txt').read_text():raise AssertionError((j.stdout,j.stderr))
 subprocess.run(['cargo','build','--quiet','--locked','--target-dir',str(root/'log4rs-prototype/target'),'--manifest-path',str(root/'log4rs-prototype/Cargo.toml')],check=True,timeout=240)
 file=d/'rust-events.log';binary=root/'log4rs-prototype/target/debug/mc-log4rs-prototype'
 subprocess.run([str(binary),str(file),'EULA_EVENT'],check=True,capture_output=True,text=True)
 if j.stderr!=file.read_text():raise AssertionError((j.stderr,file.read_text()))
 print('OK: evento WARN de Eula.class real con archivo ausente coincide con fixture log4rs; Eula sólo se ejecuta en Java')
