#!/usr/bin/env python3
"""Método Log4j 2.26.0 real, con dependencias de fixture y OSGi ausente.

Contrasta el consumo con proveedores sintéticos; no prueba el logger real. Los
stubs existen solo en el fixture, no se instalan en el traductor.
"""
import hashlib, io, os, pathlib, subprocess, tempfile, zipfile

root = pathlib.Path(__file__).resolve().parents[1]
project = root.parent
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
sources = {
'Logger.java': '''package org.apache.logging.log4j; public interface Logger { void error(String s,Throwable t); void warn(String s,Object a,Object b); }''',
'StatusLogger.java': '''package org.apache.logging.log4j.status; import org.apache.logging.log4j.Logger; public final class StatusLogger implements Logger { public static int calls,warnings; public static StatusLogger getLogger(){calls++;return null;} public void error(String s,Throwable t){} public void warn(String s,Object a,Object b){warnings++;} }''',
'StackLocatorUtil.java': '''package org.apache.logging.log4j.util; public final class StackLocatorUtil { public static int calls; public static Class<?> getCallerClass(int n){calls++;return StackLocatorUtil.class;} }''',
'Svc.java': '''package net.minecraft.test; public interface Svc {}''',
'First.java': '''package net.minecraft.test;public class First implements Svc {public First(){SafeStreamProbe.created+=1;}}''',
'Second.java': '''package net.minecraft.test;public class Second implements Svc {public Second(){SafeStreamProbe.created+=10;}}''',
'SafeStreamProbe.java': '''package net.minecraft.test;
import java.util.*;import java.util.stream.*;import org.apache.logging.log4j.util.*;import org.apache.logging.log4j.status.StatusLogger;
public class SafeStreamProbe {
 public static int created,seen,pred;
 static final class OtherSplit extends Spliterators.AbstractSpliterator<Svc>{OtherSplit(){super(0,0);}public boolean tryAdvance(java.util.function.Consumer<? super Svc> c){return false;}}
 public static Class<?> observed;
 public static int callbackStackConsumer(int n){Stream<Svc> s=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());s.filter(x->true).forEach(x->observed=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).getCallerClass());return observed.getName().startsWith("java.util.stream.")?1:0;}
 public static int callbackStackPredicate(int n){Stream<Svc> s=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());s.filter(x->{observed=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).getCallerClass();return true;}).forEach(x->{});return observed.getName().startsWith("java.util.stream.")?1:0;}
 public static int mappedGuard(int n){Stream<Svc> s=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());s.map(x->x).forEach(x->{});return 1;}
 public static int sortedGuard(int n){Stream<Svc> s=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());s.sorted(Comparator.comparing(x->Integer.valueOf(1))).forEach(x->{});return 1;}
 public static int otherSource(int n){Stream<Svc> s=StreamSupport.stream(new OtherSplit(),false);if(n==0){try{s.forEach(null);}catch(NullPointerException e){}try{s.forEach(null);return -1;}catch(IllegalStateException e){return 12;}}s.forEach(x->{});return 10;}
 public static int chainCase(int n){Stream<Svc> a=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());Stream<Svc> b=a.filter(x->true);if((n&1)!=0)a.close();if((n&2)!=0)b.close();try{b.forEach(x->seen++);return 200+seen;}catch(IllegalStateException e){return e.getMessage().equals((n&2)!=0?"stream has already been operated upon or closed":"source already consumed or closed")?300:301;}}
 public static int serviceError(int n){Stream<Svc> s=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());s.forEach(x->{throw new ServiceConfigurationError("broken");});return created*100+StatusLogger.warnings;}
 public static int throwsCase(int n){try{Stream<Svc> s=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());if((n&1)!=0)s=s.filter(x->{throw new IllegalArgumentException();});s.forEach(x->{throw new IllegalArgumentException();});return -9;}catch(IllegalArgumentException e){return created*100+StatusLogger.warnings;}}
 public static int terminal(int n){
  Stream<Svc> stream=ServiceLoaderUtil.safeStream(Svc.class,ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader()),new StatusLogger());
  if((n&1)!=0)stream=stream.filter(x->{pred++;return x instanceof First;});
  if((n&2)!=0){try{stream.forEach(null);return -1;}catch(NullPointerException e){}}
  try{stream.forEach(x->{seen=seen*3+(x instanceof First?1:2);});}catch(IllegalStateException e){return created*1000+seen*10+pred+5;}
  try{stream.forEach(x->{});return -2;}catch(IllegalStateException e){}
  return created*1000+seen*10+pred;
 }
 public static int run(int n){try{
   ServiceLoader<Svc> loader=n==0?null:ServiceLoader.load(Svc.class,SafeStreamProbe.class.getClassLoader());
   Stream<Svc> a=ServiceLoaderUtil.safeStream(n==1?null:Svc.class,loader,null);
   boolean parallel=a.isParallel(); a.close();a.close();
   return (parallel?10000:0)+StackLocatorUtil.calls*100+StatusLogger.calls;
 }catch(NullPointerException e){return 9000+StackLocatorUtil.calls*100+StatusLogger.calls;}}
}''',
'SafeStreamDriver.java': '''import net.minecraft.test.SafeStreamProbe;public class SafeStreamDriver{public static void main(String[] a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("callbackStackConsumer")?SafeStreamProbe.callbackStackConsumer(n):a[0].equals("callbackStackPredicate")?SafeStreamProbe.callbackStackPredicate(n):a[0].equals("terminal")?SafeStreamProbe.terminal(n):a[0].equals("throwsCase")?SafeStreamProbe.throwsCase(n):a[0].equals("serviceError")?SafeStreamProbe.serviceError(n):a[0].equals("chainCase")?SafeStreamProbe.chainCase(n):a[0].equals("otherSource")?SafeStreamProbe.otherSource(n):SafeStreamProbe.run(n));}}}''',
'FrameworkUtil.java': '''package org.osgi.framework;public class FrameworkUtil{}''',
}
with tempfile.TemporaryDirectory(prefix='mc-safestream-') as tmp:
 d=pathlib.Path(tmp)
 with zipfile.ZipFile(project/'downloads/server-26.3.jar') as z:
  lines=z.read('META-INF/libraries.list').decode().splitlines()
  entry=next(line.split('\t') for line in lines if 'log4j-api/2.26.0/' in line)
  api=z.read('META-INF/libraries/'+entry[2]);assert hashlib.sha256(api).hexdigest()==entry[0]
 (d/'api.jar').write_bytes(api)
 for name,text in sources.items():(d/name).write_text(text)
 subprocess.run([str(jdk/'javac'),'-cp',str(d/'api.jar'),'-d',str(d/'classes'),*[str(d/x) for x in sources]],check=True)
 real_names=['org/apache/logging/log4j/util/ServiceLoaderUtil.class','org/apache/logging/log4j/util/ServiceLoaderUtil$ServiceLoaderSpliterator.class','org/apache/logging/log4j/util/ServiceLoaderUtil$1.class','org/apache/logging/log4j/util/OsgiServiceLocator.class']
 with zipfile.ZipFile(io.BytesIO(api)) as z:real={n:z.read(n) for n in real_names}
 def archive(path,mutate=None,present=False):
  with zipfile.ZipFile(path,'w') as z:
   for f in (d/'classes').rglob('*.class'):
    n=f.relative_to(d/'classes').as_posix()
    if n=='SafeStreamDriver.class' or n=='org/osgi/framework/FrameworkUtil.class':continue
    z.write(f,n)
   for n,b in real.items():
    if n==mutate:
     # Change a UTF8 attribute string without changing the class structure.
     assert b'SourceFile' in b;b=b.replace(b'SourceFile',b'SourcfFile',1)
    z.writestr(n,b)
   z.writestr('META-INF/services/net.minecraft.test.Svc',b'net.minecraft.test.First\nnet.minecraft.test.Second\n')
   if present:z.write(d/'classes/org/osgi/framework/FrameworkUtil.class','org/osgi/framework/FrameworkUtil.class')
 archive(d/'fixture.jar');archive(d/'present.jar',present=True)
 archive(d/'altered-service.jar',real_names[0]);archive(d/'altered-osgi.jar',real_names[3]);archive(d/'altered-split.jar',real_names[1])
 driver=d/'driver';driver.mkdir();(driver/'SafeStreamDriver.class').write_bytes((d/'classes/SafeStreamDriver.class').read_bytes())
 def compile(jar,enable=True,method='run'):
  env=os.environ.copy();env.pop('MC_AOT_CLOSED_CLASSPATH',None)
  if enable:env['MC_AOT_CLOSED_CLASSPATH']='1'
  env['MC_AOT_REFLECT_CLASSES']='net/minecraft/test/First:net/minecraft/test/Second'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/jar),'net/minecraft/test/SafeStreamProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,env=env,timeout=180)
 p=compile('fixture.jar')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[0,1,2,2,1,3,0,2]*8
 java=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+os.pathsep+str(driver),'SafeStreamDriver','run',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError(('real safeStream',java.stdout,native.stdout,native.stderr))
 p=compile('fixture.jar',method='terminal')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[0,1,2,3]*16
 java=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+os.pathsep+str(driver),'SafeStreamDriver','terminal',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
 native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError(('real safeStream terminal',java.stdout,native.stdout,native.stderr))
 for method,vals in [('throwsCase',list(range(24))),('serviceError',list(range(24))),('chainCase',list(range(24))),('otherSource',[0])]:
  p=compile('fixture.jar',method=method)
  if p.returncode:raise RuntimeError(p.stderr)
  java=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+os.pathsep+str(driver),'SafeStreamDriver',method,*map(str,vals)],capture_output=True,text=True,check=True,timeout=30)
  native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
  if native.returncode or java.stdout!=native.stdout:raise AssertionError((method,java.stdout,native.stdout,native.stderr))
  if method=='otherSource':
   native=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True,timeout=30)
   if native.returncode==0 or 'solo Spliterator oficial de Log4j' not in native.stderr:raise AssertionError(('other source guard',native.stderr))
 for method in ['callbackStackConsumer','callbackStackPredicate']:
  java=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+os.pathsep+str(driver),'SafeStreamDriver',method,'0'],capture_output=True,text=True,check=True,timeout=30)
  if java.stdout!='1\n':raise AssertionError((method,'no se observó frame java.util.stream',java.stdout))
  p=compile('fixture.jar',method=method)
  if p.returncode:raise RuntimeError((method,p.stderr))
  native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
  if native.returncode==0 or 'StackWalker: frame JDK no modelado' not in native.stderr:raise AssertionError((method,'guarda de callback',native.returncode,native.stderr))
 p=compile('fixture.jar',method='mappedGuard')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True,timeout=30)
 if native.returncode==0 or 'Stream.map: consumo transformado no implementado' not in native.stderr:raise AssertionError(('mapped consumption guard',native.returncode,native.stderr))
 p=compile('fixture.jar',method='sortedGuard')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'native'),'0','1'],capture_output=True,text=True,timeout=30)
 if native.returncode==0 or 'Stream.sorted: consumo ordenado no implementado' not in native.stderr:raise AssertionError(('sorted consumption guard',native.returncode,native.stderr))
 p=compile('altered-split.jar',method='terminal')
 if p.returncode==0 or 'Spliterator Log4j versión no verificada' not in p.stderr:raise AssertionError(('spliterator hash guard',p.stderr))
 for jar,enabled,want in [('fixture.jar',False,'MC_AOT_CLOSED_CLASSPATH=1'),('present.jar',True,'FrameworkUtil presente fuera del perfil'),('altered-service.jar',True,'versión no verificada'),('altered-osgi.jar',True,'versión no verificada')]:
  p=compile(jar,enabled)
  if p.returncode==0 or want not in p.stderr:raise AssertionError((jar,enabled,p.returncode,p.stderr))
 print(f'OK: 201 resultados del safeStream oficial contra Java con stubs de fixture, filtros, forEach y excepciones; guardas de callbacks JDK, opt-in, presencia, fuente y hashes; no prueba el logger real')
