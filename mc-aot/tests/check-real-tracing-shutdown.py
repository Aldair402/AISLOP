#!/usr/bin/env python3
"""Diferencial del método oficial TracingExecutor.shutdownAndAwait, con perfil sin interrupción."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1]; jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'; inner=root.parent/'downloads/server-26.3-inner.jar'
source='''package net.minecraft.test;
import java.util.concurrent.*;import net.minecraft.TracingExecutor;import net.minecraft.core.QuartPos;
public class TracingProbe {
 static volatile int total,latch;
 public static synchronized void add(int n){total=total+QuartPos.toBlock(n);}
 public static void block(){while(latch==0)Thread.yield();}
 public static int run(int n){ForkJoinPool p=new ForkJoinPool(1);TracingExecutor t=new TracingExecutor(p);p.execute(new Job(n));t.shutdownAndAwait(5L,TimeUnit.SECONDS);return total;}
 public static int accessor(int n){ForkJoinPool p=new ForkJoinPool(1);TracingExecutor t=new TracingExecutor(p);t.service().execute(new Job(n));t.shutdownAndAwait(5L,TimeUnit.SECONDS);return total;}
 public static int iface(int n){ForkJoinPool p=new ForkJoinPool(1);TracingExecutor t=new TracingExecutor(p);Executor e=t;e.execute(new Job(n));t.shutdownAndAwait(5L,TimeUnit.SECONDS);return total;}
 public static int wrapped(int n){ForkJoinPool p=new ForkJoinPool(1);TracingExecutor t=new TracingExecutor(p);t.execute(new Job(n));t.shutdownAndAwait(5L,TimeUnit.SECONDS);return total;}
 public static int timeout(int n){latch=0;ForkJoinPool p=new ForkJoinPool(1);TracingExecutor t=new TracingExecutor(p);p.execute(new Block());t.shutdownAndAwait(0L,TimeUnit.SECONDS);return n;}
}
final class Job implements Runnable {final int n;Job(int n){this.n=n;}public void run(){TracingProbe.add(n);}}
final class Block implements Runnable {public void run(){TracingProbe.block();}}
'''
driver='''import net.minecraft.test.TracingProbe;public class Driver {public static void main(String[] a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("wrapped")?TracingProbe.wrapped(n):a[0].equals("accessor")?TracingProbe.accessor(n):a[0].equals("iface")?TracingProbe.iface(n):TracingProbe.run(n));}}}'''
vals=[0,1,-2,3,100,-101,2147483647,-2147483648,17,-9,42,2]
with tempfile.TemporaryDirectory(prefix='mc-tracing-official-') as temp:
 d=pathlib.Path(temp);(d/'TracingProbe.java').write_text(source);(d/'Driver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'TracingProbe.java'),str(d/'Driver.java')],check=True)
 with zipfile.ZipFile(inner) as z:
  for name in ['net/minecraft/TracingExecutor.class','net/minecraft/core/QuartPos.class']:
   path=d/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
 with zipfile.ZipFile(root.parent/'downloads/server-26.3.jar') as bundle:
  (d/'jtracy.jar').write_bytes(bundle.read('META-INF/libraries/com/mojang/jtracy/1.14.38/jtracy-1.14.38.jar'))
 with zipfile.ZipFile(d/'jtracy.jar') as lib:
  p=d/'com/mojang/jtracy/TracyClient.class';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(lib.read('com/mojang/jtracy/TracyClient.class'))
 def jar(name):subprocess.run([str(jdk/'jar'),'cf',str(d/name),'-C',str(d),'net','-C',str(d),'com'],check=True)
 jar('fixture.jar')
 base=os.environ.copy();base.pop('MC_AOT_RAYON_ASSUME_NO_INTERRUPT',None);base.pop('MC_AOT_RAYON_ASSUME_NO_TRACY',None)
 def compile(method,jarname='fixture.jar',allow=True,tracy=False):
  env=base.copy()
  if allow:env['MC_AOT_RAYON_ASSUME_NO_INTERRUPT']='1'
  if tracy:env['MC_AOT_RAYON_ASSUME_NO_TRACY']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/jarname),'net/minecraft/test/TracingProbe',str(d/method),method,'(I)I'],text=True,capture_output=True,env=env,timeout=90)
 p=compile('run',allow=False)
 if p.returncode==0 or 'handlers no soportados' not in p.stderr:raise AssertionError(('guardia de interrupción',p.returncode,p.stderr))
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner)+os.pathsep+str(d/'jtracy.jar'),'Driver','run',*map(str,vals)],capture_output=True,text=True,timeout=20,check=True)
 args=[]
 for v in vals:args.extend([str(v),'--phase'])
 native=subprocess.run([str(d/'run'),*args],capture_output=True,text=True,timeout=20)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('accessor')
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner)+os.pathsep+str(d/'jtracy.jar'),'Driver','accessor',*map(str,vals)],capture_output=True,text=True,timeout=20,check=True)
 native=subprocess.run([str(d/'accessor'),*args],capture_output=True,text=True,timeout=20)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError(('accessor',java.stdout,native.stdout,native.stderr))
 p=compile('wrapped')
 if p.returncode==0 or 'MC_AOT_RAYON_ASSUME_NO_TRACY=1' not in p.stderr:raise AssertionError(('guardia de Tracy',p.returncode,p.stderr))
 p=compile('wrapped',tracy=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner)+os.pathsep+str(d/'jtracy.jar'),'Driver','wrapped',*map(str,vals)],capture_output=True,text=True,timeout=20,check=True)
 native=subprocess.run([str(d/'wrapped'),*args],capture_output=True,text=True,timeout=20)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError(('wrapped',java.stdout,native.stdout,native.stderr))
 p=compile('iface',tracy=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner)+os.pathsep+str(d/'jtracy.jar'),'Driver','iface',*map(str,vals)],capture_output=True,text=True,timeout=20,check=True)
 native=subprocess.run([str(d/'iface'),*args],capture_output=True,text=True,timeout=20)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError(('iface',java.stdout,native.stdout,native.stderr))
 tracing=d/'com/mojang/jtracy/TracyClient.class';b=tracing.read_bytes();old=b'TracyClient.java';assert old in b;tracing.write_bytes(b.replace(old,b'XracyClient.java'));jar('tracy-modified.jar');tracing.write_bytes(b)
 p=compile('wrapped','tracy-modified.jar',tracy=True)
 if p.returncode==0 or 'TracyClient: versión de clase no verificada' not in p.stderr:raise AssertionError(('guardia hash Tracy',p.returncode,p.stderr))
 p=compile('timeout')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'timeout'),'1'],capture_output=True,text=True,timeout=20)
 if native.returncode==0 or 'shutdownNow no soportado' not in native.stderr:raise AssertionError(('guardia shutdownNow',native.returncode,native.stderr))
 cls=d/'net/minecraft/TracingExecutor.class';b=cls.read_bytes();old=b'TracingExecutor.java';assert old in b;cls.write_bytes(b.replace(old,b'XracingExecutor.java'));jar('modified.jar')
 p=compile('run','modified.jar')
 if p.returncode==0 or 'versión de clase no verificada' not in p.stderr:raise AssertionError(('guardia hash',p.returncode,p.stderr))
 print('OK: 48 resultados con TracingExecutor.execute/service/shutdownAndAwait, TracyClient y QuartPos oficiales frente a Java; guardas de interrupción, Tracy desactivado, timeout/shutdownNow y SHA-256')
