#!/usr/bin/env python3
"""Normalización real de Log4j 2.26.0: propiedades y entorno, con guardas."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';bundle=root.parent/'downloads/server-26.3.jar'
stub='''package org.apache.logging.log4j.status;import java.util.Map;class StatusLogger$PropertiesUtilsDouble{static Map<String,Object> readAllAvailableProperties(){return null;}static String readProperty(Map<String,Object> m,String n){return null;}}'''
src='''package org.apache.logging.log4j.status;import java.util.Map;public class Bridge{public static int run(int n){Map<String,Object> m=StatusLogger$PropertiesUtilsDouble.readAllAvailableProperties();String key;switch(n%4){case 0:key="log4j2.Foo";break;case 1:key="log4j2-BAR";break;case 2:key="log4j2.é";break;default:key="log4j2.missing";}String v=StatusLogger$PropertiesUtilsDouble.readProperty(m,key);return v==null?-1:v.length()*100+v.charAt(0);}}'''
driver='''import org.apache.logging.log4j.status.Bridge;public class PropDriver{public static void main(String[]a){for(String x:a)System.out.println(Bridge.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-log4j-properties-') as t:
 d=pathlib.Path(t)
 with zipfile.ZipFile(bundle) as z:
  names=[n for n in z.namelist() if '/log4j-api/' in n and n.endswith('.jar')];assert len(names)==1;api=z.read(names[0])
 (d/'log4j.jar').write_bytes(api);(d/'StatusLogger$PropertiesUtilsDouble.java').write_text(stub);(d/'Bridge.java').write_text(src);(d/'PropDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StatusLogger$PropertiesUtilsDouble.java'),str(d/'Bridge.java'),str(d/'PropDriver.java')],check=True)
 with zipfile.ZipFile(d/'log4j.jar') as z:
  name='org/apache/logging/log4j/status/StatusLogger$PropertiesUtilsDouble.class';(d/name).write_bytes(z.read(name))
 def mkjar():subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'org'],check=True)
 mkjar();base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'org/apache/logging/log4j/status/Bridge'];p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));env=os.environ.copy();env['LOG4J2_FOO']='environment';env['LOG4J2_BAR']='second';env['MC_AOT_JAVA_PROPERTIES']='log4j2.foo=system\nlog4j2.é=unicøde';j=subprocess.run([str(jdk/'java'),'-Dlog4j2.foo=system','-Dlog4j2.é=unicøde','-cp',str(d/'fixture.jar')+os.pathsep+str(d/'log4j.jar')+os.pathsep+str(d),'PropDriver',*map(str,vals)],env=env,capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],env=env,capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 env['log4j2.foo']='duplicate';q=subprocess.run([str(d/'native'),'0','0'],env=env,capture_output=True,text=True)
 if q.returncode==0 or 'duplicadas' not in q.stderr:raise AssertionError((q.returncode,q.stderr))
 (d/'log4j2.StatusLogger.properties').write_text('log4j2.foo=file');subprocess.run([str(jdk/'jar'),'uf',str(d/'fixture.jar'),'-C',str(d),'log4j2.StatusLogger.properties'],check=True);q=subprocess.run(base+[str(d/'bad'),'run','(I)I'],capture_output=True,text=True)
 if q.returncode==0 or 'recurso' not in q.stderr:raise AssertionError((q.returncode,q.stderr))
 print('OK: 80 consultas reales Log4j, precedencia entorno/propiedades, Unicode y guardas de recurso y colisiones')
