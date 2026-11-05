#!/usr/bin/env python3
"""Ejecuta bytecode Java de ForkJoinPool.submit(Runnable)/join sobre Rayon."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;import net.minecraft.core.QuartPos;
public class ForkFixture {
 static volatile int total;static volatile int ready;static volatile int done;static volatile ForkJoinPool sharedPool;
 public static synchronized void add(int n){total=total+n;done=done+1;}
 public static int run(int n){ForkJoinPool p=new ForkJoinPool(2);ForkJoinTask<?> f=p.submit(new Work(n));f.join();f.join();p.shutdown();p.shutdown();return total;}
 public static void signal(){ready=1;}public static void waitSignal(){while(ready==0){}}
 public static int executor(int n){ready=0;ForkJoinPool p=new ForkJoinPool(2);Executor e=p;e.execute(new Work(n));p.submit(new Waiter()).join();p.shutdown();return total;}
 public static void waitAll(int n){while(done<n){}}
 public static int batch(int n){done=0;total=0;ForkJoinPool p=new ForkJoinPool(4);for(int i=0;i<n;i++)p.execute(new Work(i));p.submit(new WaitAll(n)).join();p.shutdown();return total;}
 public static int early(int n){ForkJoinPool p=new ForkJoinPool(1);ForkJoinTask<?> f=p.submit(new Work(n));p.shutdown();f.join();return total;}
 public static int samepool(int n){sharedPool=new ForkJoinPool(1);sharedPool.submit(new Parent(n)).join();sharedPool.shutdown();return total;}
 public static void child(int n){sharedPool.submit(new Work(n)).join();}
 public static void forever(){while(true){}}
 public static int failure(int n){ForkJoinPool p=new ForkJoinPool(1);p.submit(new Forever()).join();p.shutdown();return n;}
 public static int invalid(int n){ForkJoinPool p=new ForkJoinPool(0);p.shutdown();return n;}
 public static int rejected(int n){ForkJoinPool p=new ForkJoinPool(1);p.shutdown();p.submit(new Work(n));return n;}
 public static int tooMany(int n){ForkJoinPool p=new ForkJoinPool(256);p.shutdown();return n;}
 public static int factory(int n){ForkJoinPool p=new ForkJoinPool(1,ForkJoinPool.defaultForkJoinWorkerThreadFactory,null,true);p.submit(new Work(n)).join();p.shutdown();return total;}
 public static int custom(int n){ForkJoinPool p=new ForkJoinPool(1,new CustomFactory(),null,true);p.shutdown();return n;}
}
final class CustomFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {public ForkJoinWorkerThread newThread(ForkJoinPool p){return ForkJoinPool.defaultForkJoinWorkerThreadFactory.newThread(p);}}
final class Forever implements Runnable {public void run(){ForkFixture.forever();}}
final class WaitAll implements Runnable {final int n;WaitAll(int n){this.n=n;}public void run(){ForkFixture.waitAll(n);}}
final class Waiter implements Runnable {public void run(){ForkFixture.waitSignal();}}
final class Parent implements Runnable {final int n;Parent(int n){this.n=n;}public void run(){ForkFixture.child(n);}}
final class Work implements Runnable {final int n;Work(int n){this.n=n;}public void run(){ForkFixture.add(QuartPos.toBlock(n));ForkFixture.signal();}}
'''
driver='''import net.minecraft.test.ForkFixture;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++)System.out.println(a[0].equals("nested")?ForkFixture.samepool(Integer.parseInt(a[i])):a[0].equals("executor")?ForkFixture.executor(Integer.parseInt(a[i])):a[0].equals("batch")?ForkFixture.batch(Integer.parseInt(a[i])):a[0].equals("early")?ForkFixture.early(Integer.parseInt(a[i])):a[0].equals("factory")?ForkFixture.factory(Integer.parseInt(a[i])):ForkFixture.run(Integer.parseInt(a[i])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-rayon-fork-bytecode-') as temp:
 d=pathlib.Path(temp);(d/'ForkFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 inner=root.parent/'downloads/server-26.3-inner.jar'
 subprocess.run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'ForkFixture.java'),str(d/'Driver.java')],check=True)
 with zipfile.ZipFile(inner) as srcjar:
  real=d/'net/minecraft/core/QuartPos.class';real.parent.mkdir(parents=True,exist_ok=True);real.write_bytes(srcjar.read('net/minecraft/core/QuartPos.class'))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method,out):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/ForkFixture',str(out),method,'(I)I'],text=True,capture_output=True)
 p=compile('run',d/'native');
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[0,1,-2,3,100,-101,2147483647,-2147483648,17,-9,42,2]
 j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver','normal',*map(str,vals)],text=True,capture_output=True,check=True,timeout=20)
 args=[]
 for v in vals:args.extend([str(v),'--phase'])
 r=subprocess.run([str(d/'native'),*args],text=True,capture_output=True,check=True,timeout=20)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 p=compile('samepool',d/'nested');
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver','nested',*map(str,vals)],text=True,capture_output=True,check=True,timeout=20)
 r=subprocess.run([str(d/'nested'),*args],text=True,capture_output=True,check=True,timeout=20)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 p=compile('executor',d/'executor');
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver','executor',*map(str,vals)],text=True,capture_output=True,check=True,timeout=20)
 r=subprocess.run([str(d/'executor'),*args],text=True,capture_output=True,check=True,timeout=20)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 p=compile('early',d/'early');
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver','early',*map(str,vals)],text=True,capture_output=True,check=True,timeout=20)
 r=subprocess.run([str(d/'early'),*args],text=True,capture_output=True,check=True,timeout=20)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 p=compile('batch',d/'batch');
 if p.returncode:raise RuntimeError(p.stderr)
 batch=[0,1,2,10,30,50]*3
 j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver','batch',*map(str,batch)],text=True,capture_output=True,check=True,timeout=20)
 batchargs=[]
 for v in batch:batchargs.extend([str(v),'--phase'])
 r=subprocess.run([str(d/'batch'),*batchargs],text=True,capture_output=True,check=True,timeout=20)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 p=compile('factory',d/'factory');
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver','factory',*map(str,vals)],text=True,capture_output=True,check=True,timeout=20)
 r=subprocess.run([str(d/'factory'),*args],text=True,capture_output=True,check=True,timeout=20)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 p=compile('failure',d/'failure');
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'failure'),'1'],text=True,capture_output=True,timeout=15)
 if r.returncode==0 or 'StepLimit' not in r.stderr:raise AssertionError((r.returncode,r.stderr))
 p=compile('invalid',d/'invalid');
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'invalid'),'1'],text=True,capture_output=True,timeout=10)
 if r.returncode==0 or 'paralelismo fuera del perfil' not in r.stderr:raise AssertionError((r.returncode,r.stderr))
 p=compile('rejected',d/'rejected');
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'rejected'),'1'],text=True,capture_output=True,timeout=10)
 if r.returncode==0 or 'pool cerrado' not in r.stderr:raise AssertionError((r.returncode,r.stderr))
 p=compile('tooMany',d/'tooMany');
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'tooMany'),'1'],text=True,capture_output=True,timeout=10)
 if r.returncode==0 or 'paralelismo fuera del perfil' not in r.stderr:raise AssertionError((r.returncode,r.stderr))
 p=compile('custom',d/'custom');
 if p.returncode==0:raise AssertionError('La factory personalizada Java no debe aceptarse')
 print('OK: 78 decisiones y 279 tareas por execute con Runnable de bytecode Java que ejecutan QuartPos.toBlock oficial, incluidos execute por interfaz y joins anidados en un pool de un hilo, sobre Rayon, resultados contrastados con ForkJoinPool Java; join repetido y tras shutdown, y guardas de fallo de tarea, paralelismo, cierre y factory personalizada')
