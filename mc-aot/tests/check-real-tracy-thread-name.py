#!/usr/bin/env python3
"""TracyClient oficial desactivado: setThreadName y worker sintético; no Tracy activo."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;import com.mojang.jtracy.TracyClient;
public class TracyNameProbe {
 static volatile int started,stopped,total;
 public static synchronized void start(int n){started+=n;}
 public static synchronized void stop(){stopped++;}
 public static synchronized void work(int n){total+=n;}
 public static int run(int n) throws InterruptedException {String name="Worker-\\uD83D\\uDE80";ForkJoinPool p=new ForkJoinPool(1,new Factory(name),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -1;return total+started+stopped;}
 public static int nullName(int n){TracyClient.setThreadName(null,n);return n;}
}
final class Factory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final String name;Factory(String n){name=n;}public ForkJoinWorkerThread newThread(ForkJoinPool p){ForkJoinWorkerThread w=new Worker(p,name);w.setName(name);return w;}}
final class Worker extends ForkJoinWorkerThread {final String name;Worker(ForkJoinPool p,String n){super(p);name=n;}protected void onStart(){TracyClient.setThreadName(name,name.hashCode());TracyNameProbe.start(getName().hashCode());super.onStart();}protected void onTermination(Throwable t){TracyNameProbe.stop();super.onTermination(t);}}
final class Job implements Runnable {final int n;Job(int n){this.n=n;}public void run(){TracyNameProbe.work(n);}}
'''
driver='''import net.minecraft.test.TracyNameProbe;import com.mojang.jtracy.TracyClient;public class Driver{public static void main(String[]a)throws Exception{if(TracyClient.isAvailable())throw new AssertionError("Tracy está activo");for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("run")?TracyNameProbe.run(n):TracyNameProbe.nullName(n));}}}'''
vals=[0,1,-2,3,100,-101,2147483647,-2147483648,17,-9,42,2]
with tempfile.TemporaryDirectory(prefix='mc-tracy-name-') as temp:
 d=pathlib.Path(temp);(d/'TracyNameProbe.java').write_text(source);(d/'Driver.java').write_text(driver)
 with zipfile.ZipFile(root.parent/'downloads/server-26.3.jar') as z:(d/'jtracy.jar').write_bytes(z.read('META-INF/libraries/com/mojang/jtracy/1.14.38/jtracy-1.14.38.jar'))
 subprocess.run([str(jdk/'javac'),'-cp',str(d/'jtracy.jar'),'-d',str(d),str(d/'TracyNameProbe.java'),str(d/'Driver.java')],check=True)
 with zipfile.ZipFile(d/'jtracy.jar') as z:
  name='com/mojang/jtracy/TracyClient.class';data=z.read(name)
  assert hashlib.sha256(data).hexdigest()=='55d6a5576bd91504ebdea28af611a243aa5e0b1f288d78241f788e34c0c2f3a1'
  path=d/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 def jar(filename):subprocess.run([str(jdk/'jar'),'cf',str(d/filename),'-C',str(d),'net','-C',str(d),'com'],check=True)
 jar('fixture.jar')
 base=os.environ.copy();base.pop('MC_AOT_RAYON_ASSUME_NO_TRACY',None)
 def compile(method,allow=False,archive='fixture.jar'):
  env=base.copy()
  if allow:env['MC_AOT_RAYON_ASSUME_NO_TRACY']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/archive),'net/minecraft/test/TracyNameProbe',str(d/method),method,'(I)I'],text=True,capture_output=True,env=env,timeout=120)
 p=compile('run')
 if p.returncode==0 or 'MC_AOT_RAYON_ASSUME_NO_TRACY=1' not in p.stderr:raise AssertionError(('guardia de Tracy',p.returncode,p.stderr))
 args=[]
 for n in vals:args.extend([str(n),'--phase'])
 for method in ('run','nullName'):
  p=compile(method,True)
  if p.returncode:raise RuntimeError(p.stderr)
  java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(d/'jtracy.jar'),'Driver',method,*map(str,vals)],text=True,capture_output=True,check=True,timeout=30)
  native=subprocess.run([str(d/method),*args],text=True,capture_output=True,timeout=30)
  if native.returncode or java.stdout!=native.stdout:raise AssertionError((method,java.stdout,native.stdout,native.stderr))
 path.write_bytes(data.replace(b'TracyClient.java',b'XracyClient.java'));jar('modified.jar')
 p=compile('run',True,'modified.jar')
 if p.returncode==0 or 'TracyClient: versión de clase no verificada' not in p.stderr:raise AssertionError(('guardia hash Tracy',p.returncode,p.stderr))
 print('OK: 24 resultados con TracyClient.setThreadName oficial desactivado, null y callback de worker sintético; guardas de opt-in y SHA-256')
