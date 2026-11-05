#!/usr/bin/env python3
"""Descubre el proveedor real SLF4J del bundle sin simular su construcción."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];workspace=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
probe='''package net.minecraft.test;import java.util.*;import org.slf4j.spi.SLF4JServiceProvider;public class RealServiceProbe {static Iterator<SLF4JServiceProvider> it;public static int run(int n){if(n==0){it=ServiceLoader.load(SLF4JServiceProvider.class,RealServiceProbe.class.getClassLoader()).iterator();return it.hasNext()?1:0;}SLF4JServiceProvider p=it.next();return p.getClass().getName().equals("org.apache.logging.slf4j.SLF4JServiceProvider")&&p.getRequestedApiVersion().equals("2.0.99")&&p.getLoggerFactory()==null&&p.getMarkerFactory()==null&&p.getMDCAdapter()==null?2:0;}}'''
driver='''import net.minecraft.test.RealServiceProbe;public class RealServiceDriver{public static void main(String[] a){System.out.println(RealServiceProbe.run(0));System.out.println(RealServiceProbe.run(1));}}'''
with tempfile.TemporaryDirectory(prefix='mc-real-slf4j-svc-') as t:
 d=pathlib.Path(t);libs=[]
 with zipfile.ZipFile(workspace/'downloads/server-26.3.jar') as original:
  lines=original.read('META-INF/libraries.list').decode();
  for i,line in enumerate(lines.splitlines()):
   digest,coord,path=line.split('\t');data=original.read('META-INF/libraries/'+path)
   if hashlib.sha256(data).hexdigest()!=digest:raise AssertionError(coord)
   p=d/f'lib{i}.jar';p.write_bytes(data);libs.append((coord,path,p))
 api=next(p for coord,_,p in libs if coord.startswith('org.slf4j:slf4j-api:'))
 (d/'RealServiceProbe.java').write_text(probe);(d/'RealServiceDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(api),'-d',str(d/'classes'),str(d/'RealServiceProbe.java'),str(d/'RealServiceDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'version.jar'),'-C',str(d/'classes'),'.'],check=True)
 with zipfile.ZipFile(d/'bundle.jar','w') as z:
  data=(d/'version.jar').read_bytes();z.writestr('META-INF/versions.list',f'{hashlib.sha256(data).hexdigest()}\tversion\tv/version.jar\n');z.writestr('META-INF/versions/v/version.jar',data);z.writestr('META-INF/libraries.list',lines)
  for _,path,p in libs:z.writestr('META-INF/libraries/'+path,p.read_bytes())
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'bundle.jar'),'net/minecraft/test/RealServiceProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d/'version.jar')]+[str(p) for _,_,p in libs]),'RealServiceDriver'],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,check=True).stdout
 if java.splitlines()[0]!=native.strip() or java!='1\n2\n':raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','0','0','1'],capture_output=True,text=True)
 if p.returncode!=2 or 'proveedor no registrado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 env=dict(os.environ,MC_AOT_REFLECT_CLASSES='org/apache/logging/slf4j/SLF4JServiceProvider')
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'bundle.jar'),'net/minecraft/test/RealServiceProbe',str(d/'registered'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 registered=subprocess.run([str(d/'registered'),'0','0','0','1'],capture_output=True,text=True,check=True).stdout
 if java!=registered:raise AssertionError((java,registered))
 print('OK: el proveedor real de Log4j se descubre e instancia desde META-INF/services; getClass, versión y tres getters previos a initialize coinciden con Java. Sin registro se aborta; initialize no probado.')
