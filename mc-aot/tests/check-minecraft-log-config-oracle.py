#!/usr/bin/env python3
"""Observa filtro y nivel del XML oficial; no prueba log4rs."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];workspace=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-log-xml-oracle-') as t:
 d=pathlib.Path(t);libs=[]
 with zipfile.ZipFile(workspace/'downloads/server-26.3.jar') as z:
  for i,line in enumerate(z.read('META-INF/libraries.list').decode().splitlines()):
   sha,_,path=line.split('\t');b=z.read('META-INF/libraries/'+path)
   if hashlib.sha256(b).hexdigest()!=sha:raise AssertionError(path+' checksum')
   p=d/f'{i}.jar';p.write_bytes(b);libs.append(p)
   if path.startswith('com/mojang/logging/'):
    import io
    with zipfile.ZipFile(io.BytesIO(b)) as lib:(d/'official-log4j2.xml').write_bytes(lib.read('log4j2.xml'))
 cp=os.pathsep.join(map(str,libs));subprocess.run([str(jdk/'javac'),'-cp',cp,'-d',str(d),str(root/'tests/MinecraftLogConfigOracle.java')],check=True)
 j=subprocess.run([str(jdk/'java'),'-Dlog4j2.configurationFile='+str(d/'official-log4j2.xml'),'-cp',str(d)+os.pathsep+cp,'MinecraftLogConfigOracle'],cwd=d,capture_output=True,text=True,check=True,timeout=60)
 h=lambda s:s.encode().hex();name=h('net.minecraft.test.MarkerProbe')
 expected=''.join(f'{level}|{name}|{h(msg)}\n' for level,msg in [('INFO','unmarked'),('INFO','allowed'),('WARN','warning')])
 if j.stdout!=expected or j.stderr!='enabled|true|true|true\n':raise AssertionError((j.stdout,j.stderr,expected))
 subprocess.run(['cargo','build','--quiet','--locked','--target-dir',str(root/'log4rs-prototype/target'),'--manifest-path',str(root/'log4rs-prototype/Cargo.toml')],check=True,timeout=240)
 native_file=d/'native-events.log';binary=root/'log4rs-prototype/target/debug/mc-log4rs-prototype'
 n=subprocess.run([str(binary),str(native_file),'MARKER_EVENT'],capture_output=True,text=True,check=True)
 if native_file.read_text()!=j.stdout or n.stderr!=j.stderr:raise AssertionError((j.stdout,native_file.read_text(),j.stderr,n.stderr))
 print('OK: fixture log4rs del filtro raíz coincide con XML oficial: INFO/WARN, DEBUG, NETWORK_PACKETS directo/heredado e isEnabled; no implementa Marker mutable ni XML')
