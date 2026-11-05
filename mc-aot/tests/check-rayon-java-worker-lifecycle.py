#!/usr/bin/env python3
"""Factory y callbacks Java reales traducidos; perfil cerrado, no la factory Minecraft."""
import os,pathlib,re,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';inner=root.parent/'downloads/server-26.3-inner.jar'
source='''package net.minecraft.test;
import java.util.concurrent.*;import java.util.concurrent.atomic.AtomicInteger;import net.minecraft.core.QuartPos;
public class LifecycleFixture {
 static volatile int starts,stops,total,latch,checksum,names;static volatile AtomicInteger counter;static volatile String text;
 public static synchronized void started(){starts=starts+1;}
 public static synchronized void nameStart(int n){names=names+n;starts=starts+1;}
 public static synchronized void stopped(){stops=stops+1;}
 public static synchronized void work(int n){if(starts!=stops+1)total=total+1000000;total=total+QuartPos.toBlock(n);}
 public static int run(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1,new Factory(),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -999;return total+starts+stops;}
 public static int noWork(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1,new Factory(),null,true);p.shutdown();if(!p.awaitTermination(0L,TimeUnit.SECONDS))return -999;return starts+stops+n;}
 public static synchronized void plain(int n){total=total+QuartPos.toBlock(n);}
 public static int service(int n) throws InterruptedException {ExecutorService e=new ForkJoinPool(1);e.execute(new Plain(n));e.shutdown();if(!e.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total;}
 public static int concatName(int n){String base;if(n==0)base=null;else if(n==1)base="";else base="X\\000\\uD800\\uD83D\\uDE80";String result="Worker-"+base+"-"+n;TextHolder h=new TextHolder(result);return h.score();}
 public static int stringLiteral(int n){if(n==0)text="";else if(n==1)text="A";else if(n==-2)text="\\u03B1\\u03B2\\uD83D\\uDE80";else text="A\\000\\uD83D\\uDE80\\uD800";TextHolder h=new TextHolder(text);return n+h.score();}
 public static void waitLatch(){while(latch==0){Thread.yield();}}
 public static synchronized void record(int n){checksum=checksum+n;}
 public static int atomic(int n) throws InterruptedException {checksum=0;counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(4);p.execute(new CounterJob(counter));p.execute(new CounterJob(counter));p.execute(new CounterJob(counter));p.execute(new CounterJob(counter));p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return counter.get()+checksum;}
 public static int freshIdentity(int n){String prefix="Fresh";String a=prefix+n;String b=prefix+n;if(a==b)return -1;if(a!=b)return a.hashCode()+b.hashCode();return -2;}
 public static int referenceBranches(int n){String a=(n&1)==0?"same":null;String b=(n&2)==0?"same":null;if(a==b)return n+10;if(a!=b)return n-10;return 7;}
 public static int nullBranches(int n){String text=n<0?null:"X";if(text==null)return n-1;if(text!=null)return n+1;return 7;}
 public static int lambdaPair(int n) throws InterruptedException {String group="Pair\\uD83D\\uDE80";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{String name="Worker-"+group+"-"+counter.getAndIncrement();ForkJoinWorkerThread w=new TwoNameWorker(pool,name,group);w.setName(name);return w;},null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names+counter.get();}
 public static int lambdaAnonymous(int n) throws InterruptedException {String group="Anonymous";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{String name="Worker-"+group+"-"+counter.getAndIncrement();ForkJoinWorkerThread w=new ForkJoinWorkerThread(pool){protected void onStart(){LifecycleFixture.nameStart(name.hashCode()+group.hashCode()+getName().hashCode());}protected void onTermination(Throwable t){LifecycleFixture.stopped();}};w.setName(name);return w;},null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names+counter.get();}
 public static int lambdaRename(int n) throws InterruptedException {String group="Group\\uD83D\\uDE80";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{String name="Worker-"+group+"-"+counter.getAndIncrement();ForkJoinWorkerThread w=new RenameWorker(pool,name);w.setName(name);return w;},null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names+counter.get();}
 public static int baseRename(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1,new BaseRenameFactory("Base"),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names;}
 public static int renamedFactory(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1,new RenameFactory("Named\\uD83D\\uDE80"),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names;}
 public static int noExplicitName(int n){ForkJoinPool p=new ForkJoinPool(1,new DefaultNameFactory("default"),null,true);p.submit(new Job(n)).join();p.shutdown();return n;}
 public static int nameSurrogate(int n){ForkJoinPool p=new ForkJoinPool(1,new RenameFactory("Bad\\uD800"),null,true);p.submit(new Job(n)).join();p.shutdown();return n;}
 public static int badRenameLambda(int n){String group="Group";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{String name="Worker-"+group+"-"+counter.getAndIncrement();ForkJoinWorkerThread w=new RenameWorker(pool,name);w.setName("different");return w;},null,true);p.submit(new Job(n)).join();p.shutdown();return n;}
 public static int nameNul(int n){ForkJoinPool p=new ForkJoinPool(1,new RenameFactory("Bad\\000Name"),null,true);p.submit(new Job(n)).join();p.shutdown();return n;}
 public static int lambdaOrdered(int n) throws InterruptedException {String name="Group\\uD83D\\uDE80";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->new NamedWorker(pool,"Worker-"+name+"-"+counter.getAndIncrement()),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names+counter.get();}
 public static int lambdaTwo(int n) throws InterruptedException {String name="Lambda\\uD83D\\uDE80";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{counter.getAndIncrement();return new NamedWorker(pool,name);},null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names+counter.get();}
 public static int lambdaFactory(int n) throws InterruptedException {String name="Lambda\\uD83D\\uDE80";ForkJoinPool p=new ForkJoinPool(1,pool->new NamedWorker(pool,name),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names;}
 public static int namedFactory(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1,new NameFactory("Worker\\uD83D\\uDE80"),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return total+starts+stops+names;}
 public static int capturedFactory(int n) throws InterruptedException {AtomicInteger c=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,new CounterFactory(c),null,true);p.submit(new Job(n)).join();p.shutdown();if(!p.awaitTermination(5L,TimeUnit.SECONDS))return -300;return c.get()+total+starts+stops;}
 public static int atomicSingle(int n){AtomicInteger a=new AtomicInteger(n);return a.getAndIncrement()+a.get();}
 public static int nullTask(int n){Executor e=new Ignoring();e.execute(null);return n;}
 public static int recordBox(int n) throws InterruptedException {PoolBox box=new PoolBox(new ForkJoinPool(1));box.close();box.waitFor((long)n,TimeUnit.SECONDS);return n;}
 public static int longArg(int n) throws InterruptedException {return longHelper((long)n);}
 public static int longHelper(long n) throws InterruptedException {long local=n;ForkJoinPool p=new ForkJoinPool(1);p.shutdown();if(p.awaitTermination(local,TimeUnit.MILLISECONDS))return 1;return 0;}
 public static int units(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1);if(p.awaitTermination(-1L,TimeUnit.SECONDS))return -1;p.shutdown();if(!p.awaitTermination(9223372036854775807L,TimeUnit.DAYS))return -2;if(!p.awaitTermination(9223372036854775807L,TimeUnit.HOURS))return -3;if(!p.awaitTermination(9223372036854775807L,TimeUnit.MINUTES))return -4;if(!p.awaitTermination(9223372036854775807L,TimeUnit.SECONDS))return -5;if(!p.awaitTermination(9223372036854775807L,TimeUnit.MILLISECONDS))return -6;if(!p.awaitTermination(9223372036854775807L,TimeUnit.MICROSECONDS))return -7;if(!p.awaitTermination(9223372036854775807L,TimeUnit.NANOSECONDS))return -8;return n+1;}
 public static int timed(int n) throws InterruptedException {latch=0;ForkJoinPool p=new ForkJoinPool(1);p.submit(new Block());p.shutdown();boolean first=p.awaitTermination(1L,TimeUnit.MILLISECONDS);latch=1;boolean last=p.awaitTermination(5L,TimeUnit.SECONDS);if(first)return -200;if(!last)return -300;return n+1;}
 public static int open(int n) throws InterruptedException {ForkJoinPool p=new ForkJoinPool(1);boolean first=p.awaitTermination(0L,TimeUnit.DAYS);p.shutdown();boolean last=p.awaitTermination((long)n,TimeUnit.MILLISECONDS);if(first)return -200;if(!last)return -300;return n+1;}
 public static int many(int n){ForkJoinPool p=new ForkJoinPool(2,new Factory(),null,true);p.shutdown();return n;}
 public static int modeFalse(int n){ForkJoinPool p=new ForkJoinPool(1,new Factory(),null,false);p.shutdown();return n;}
 public static int badWorker(int n){ForkJoinPool p=new ForkJoinPool(1,new BadWorkerFactory(),null,true);p.shutdown();return n;}
 public static int badLambdaTwo(int n){String name="name";AtomicInteger c=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{c.getAndIncrement();c.getAndIncrement();return new NamedWorker(pool,name);},null,true);p.shutdown();return n;}
 public static int badAlt(int n){String name="name";ForkJoinPool.ForkJoinWorkerThreadFactory f=(ForkJoinPool.ForkJoinWorkerThreadFactory & java.io.Serializable)(pool->new NamedWorker(pool,name));ForkJoinPool p=new ForkJoinPool(1,f,null,true);p.shutdown();return n;}
 public static int badLambda(int n){String name="name";ForkJoinPool p=new ForkJoinPool(1,pool->{started();return new NamedWorker(pool,name);},null,true);p.shutdown();return n;}
 public static int badConcat(int n){String x="N"+n;return x.hashCode();}
 public static int badNamedWorker(int n){ForkJoinPool p=new ForkJoinPool(1,new BadNameFactory("name"),null,true);p.shutdown();return n;}
 public static int badAtomicFactory(int n){ForkJoinPool p=new ForkJoinPool(1,new BadAtomicFactory(new AtomicInteger(n)),null,true);p.shutdown();return n;}
 public static int mutableFactory(int n){ForkJoinPool p=new ForkJoinPool(1,new MutableFactory(new AtomicInteger(n)),null,true);p.shutdown();return n;}
 public static int badFactory(int n){ForkJoinPool p=new ForkJoinPool(1,new ImpureFactory(),null,true);p.shutdown();return n;}
}
final class TextHolder {final String value;TextHolder(String s){value=s;}int score(){return value.hashCode()+value.length();}}
final class CounterJob implements Runnable {final AtomicInteger counter;CounterJob(AtomicInteger c){counter=c;}public void run(){for(int i=0;i<100;i++)LifecycleFixture.record(counter.getAndIncrement());}}
final class Ignoring implements Executor {public void execute(Runnable r){}}
record PoolBox(ExecutorService service) {void close(){service.shutdown();} void waitFor(long t,TimeUnit u) throws InterruptedException {service.awaitTermination(t,u);}}
final class Plain implements Runnable {final int n;Plain(int n){this.n=n;}public void run(){LifecycleFixture.plain(n);}}
final class Block implements Runnable {public void run(){LifecycleFixture.waitLatch();}}
final class BadAtomicFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final AtomicInteger counter;BadAtomicFactory(AtomicInteger c){counter=c;}public ForkJoinWorkerThread newThread(ForkJoinPool pool){counter.incrementAndGet();return new Worker(pool);}}
final class MutableFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {AtomicInteger counter;MutableFactory(AtomicInteger c){counter=c;}public ForkJoinWorkerThread newThread(ForkJoinPool pool){counter.getAndIncrement();return new Worker(pool);}}
final class BadNameFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final String name;BadNameFactory(String n){name=n;}public ForkJoinWorkerThread newThread(ForkJoinPool pool){return new BadNamedWorker(pool,name);}}
final class BadNamedWorker extends ForkJoinWorkerThread {String name;BadNamedWorker(ForkJoinPool p,String n){super(p);name=n;}protected void onStart(){}protected void onTermination(Throwable t){}}
final class DefaultNameFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final String name;DefaultNameFactory(String n){name=n;}public ForkJoinWorkerThread newThread(ForkJoinPool p){return new RenameWorker(p,name);}}
final class BaseRenameFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final String name;BaseRenameFactory(String n){name=n;}public ForkJoinWorkerThread newThread(ForkJoinPool p){ForkJoinWorkerThread w=new RenameWorker(p,name);w.setName(name);return w;}}
final class RenameFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final String name;RenameFactory(String n){name=n;}public ForkJoinWorkerThread newThread(ForkJoinPool p){RenameWorker w=new RenameWorker(p,name);w.setName(name);return w;}}
final class TwoNameWorker extends ForkJoinWorkerThread {final String name;final String group;TwoNameWorker(ForkJoinPool p,String n,String g){super(p);name=n;group=g;}protected void onStart(){LifecycleFixture.nameStart(name.hashCode()+group.hashCode()+getName().hashCode());}protected void onTermination(Throwable t){LifecycleFixture.stopped();}}
final class RenameWorker extends ForkJoinWorkerThread {final String name;RenameWorker(ForkJoinPool p,String n){super(p);name=n;}protected void onStart(){super.onStart();LifecycleFixture.nameStart(getName().hashCode()+(getName()==name?7:-7));}protected void onTermination(Throwable t){LifecycleFixture.stopped();super.onTermination(t);}}
final class NameFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final String name;NameFactory(String n){name=n;}public ForkJoinWorkerThread newThread(ForkJoinPool pool){return new NamedWorker(pool,name);}}
final class NamedWorker extends ForkJoinWorkerThread {final String name;NamedWorker(ForkJoinPool p,String n){super(p);name=n;}protected void onStart(){super.onStart();LifecycleFixture.nameStart(name.hashCode());}protected void onTermination(Throwable t){LifecycleFixture.stopped();super.onTermination(t);}}
final class CounterFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {final AtomicInteger counter;CounterFactory(AtomicInteger c){counter=c;}public ForkJoinWorkerThread newThread(ForkJoinPool pool){counter.getAndIncrement();return new Worker(pool);}}
final class Factory implements ForkJoinPool.ForkJoinWorkerThreadFactory {public ForkJoinWorkerThread newThread(ForkJoinPool pool){return new Worker(pool);}}
final class Worker extends ForkJoinWorkerThread {Worker(ForkJoinPool p){super(p);}protected void onStart(){super.onStart();LifecycleFixture.started();}protected void onTermination(Throwable t){LifecycleFixture.stopped();super.onTermination(t);}}
final class BadWorkerFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {public ForkJoinWorkerThread newThread(ForkJoinPool pool){return new BadWorker(pool);}}
final class BadWorker extends ForkJoinWorkerThread {BadWorker(ForkJoinPool p){super(p);}public void run(){}protected void onStart(){}protected void onTermination(Throwable t){}}
final class ImpureFactory implements ForkJoinPool.ForkJoinWorkerThreadFactory {public ForkJoinWorkerThread newThread(ForkJoinPool pool){LifecycleFixture.started();return new Worker(pool);}}
final class Job implements Runnable {final int n;Job(int n){this.n=n;}public void run(){LifecycleFixture.work(n);}}
'''
driver='''import net.minecraft.test.LifecycleFixture;public class Driver{public static void main(String[]a) throws Exception {for(int i=1;i<a.length;i++)System.out.println(a[0].equals("nowork")?LifecycleFixture.noWork(Integer.parseInt(a[i])):a[0].equals("timed")?LifecycleFixture.timed(Integer.parseInt(a[i])):a[0].equals("open")?LifecycleFixture.open(Integer.parseInt(a[i])):a[0].equals("service")?LifecycleFixture.service(Integer.parseInt(a[i])):a[0].equals("units")?LifecycleFixture.units(Integer.parseInt(a[i])):a[0].equals("long")?LifecycleFixture.longArg(Integer.parseInt(a[i])):a[0].equals("record")?LifecycleFixture.recordBox(Integer.parseInt(a[i])):a[0].equals("null")?LifecycleFixture.nullTask(Integer.parseInt(a[i])):a[0].equals("atomic")?LifecycleFixture.atomic(Integer.parseInt(a[i])):a[0].equals("atomicsingle")?LifecycleFixture.atomicSingle(Integer.parseInt(a[i])):a[0].equals("captured")?LifecycleFixture.capturedFactory(Integer.parseInt(a[i])):a[0].equals("string")?LifecycleFixture.stringLiteral(Integer.parseInt(a[i])):a[0].equals("named")?LifecycleFixture.namedFactory(Integer.parseInt(a[i])):a[0].equals("lambda")?LifecycleFixture.lambdaFactory(Integer.parseInt(a[i])):a[0].equals("lambda2")?LifecycleFixture.lambdaTwo(Integer.parseInt(a[i])):a[0].equals("concat")?LifecycleFixture.concatName(Integer.parseInt(a[i])):a[0].equals("ordered")?LifecycleFixture.lambdaOrdered(Integer.parseInt(a[i])):a[0].equals("renamed")?LifecycleFixture.renamedFactory(Integer.parseInt(a[i])):a[0].equals("base")?LifecycleFixture.baseRename(Integer.parseInt(a[i])):a[0].equals("renameLambda")?LifecycleFixture.lambdaRename(Integer.parseInt(a[i])):a[0].equals("pair")?LifecycleFixture.lambdaPair(Integer.parseInt(a[i])):a[0].equals("anonymous")?LifecycleFixture.lambdaAnonymous(Integer.parseInt(a[i])):a[0].equals("nullBranches")?LifecycleFixture.nullBranches(Integer.parseInt(a[i])):a[0].equals("referenceBranches")?LifecycleFixture.referenceBranches(Integer.parseInt(a[i])):a[0].equals("freshIdentity")?LifecycleFixture.freshIdentity(Integer.parseInt(a[i])):LifecycleFixture.run(Integer.parseInt(a[i])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-java-worker-hooks-') as temp:
 d=pathlib.Path(temp);(d/'LifecycleFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'LifecycleFixture.java'),str(d/'Driver.java')],check=True)
 # Close this *synthetic* anonymous class for the profile: javac emits it non-final.
 # Change only ACC_FINAL; Java and AOT run the identical patched class bytes.
 anon=d/'net/minecraft/test/LifecycleFixture$1.class'; data=bytearray(anon.read_bytes()); count=int.from_bytes(data[8:10],'big'); pos=10; i=1
 while i<count:
  tag=data[pos];pos+=1
  if tag==1: size=2+int.from_bytes(data[pos:pos+2],'big')
  elif tag in (3,4,9,10,11,12,17,18): size=4
  elif tag in (5,6): size=8;i+=1
  elif tag in (7,8,16,19,20): size=2
  elif tag==15:size=3
  else:raise ValueError(('constant pool',tag))
  pos+=size;i+=1
 flags=int.from_bytes(data[pos:pos+2],'big');data[pos:pos+2]=(flags|0x10).to_bytes(2,'big');anon.write_bytes(data)
 # Compare instruction offsets, opcodes and local slots against Mojang's real
 # lambda and pre-super field initialization, ignoring constant-pool indices.
 # The callbacks and class flags still differ: this is NOT the official worker.
 def bytecode(cp,cls,method_pattern):
  text=subprocess.run([str(jdk/'javap'),'-p','-c','-classpath',str(cp),cls],text=True,capture_output=True,check=True).stdout
  match=re.search(r'^  '+method_pattern+r'[^\n]*\n    Code:\n(.*?)(?=\n\s*\n|\n})',text,re.M|re.S)
  if not match:raise AssertionError(('method not found',cls,method_pattern,text))
  return [re.sub(r'#\d+','#CP',m.group(1).split('//')[0]).strip() for line in match.group(1).splitlines() if (m:=re.match(r'^\s*(\d+:\s+.*)',line))]
 ours=bytecode(d,'net.minecraft.test.LifecycleFixture',r'private static .*lambda\$lambdaAnonymous\$\d+\(')
 actual=bytecode(inner,'net.minecraft.util.Util',r'private static .*lambda\$makeExecutor\$0\(')
 if ours!=actual:raise AssertionError(('lambda opcode mismatch',ours,actual))
 ours=bytecode(d,'net.minecraft.test.LifecycleFixture$1',r'net\.minecraft\.test\.LifecycleFixture\$1\(')
 actual=bytecode(inner,'net.minecraft.util.Util$2',r'net\.minecraft\.util\.Util\$2\(')
 if ours!=actual:raise AssertionError(('constructor opcode mismatch',ours,actual))
 with zipfile.ZipFile(inner) as z:
  path=d/'net/minecraft/core/QuartPos.class';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read('net/minecraft/core/QuartPos.class'))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/LifecycleFixture',str(d/method),method,'(I)I'],text=True,capture_output=True)
 vals=[0,1,-2,3,100,-101,2147483647,-2147483648,17,-9,42,2];args=[]
 for v in vals:args.extend([str(v),'--phase'])
 for method,label in [('run','run'),('noWork','nowork'),('timed','timed'),('open','open'),('service','service'),('units','units'),('longArg','long'),('recordBox','record'),('nullTask','null'),('atomic','atomic'),('atomicSingle','atomicsingle'),('capturedFactory','captured'),('stringLiteral','string'),('namedFactory','named'),('lambdaFactory','lambda'),('lambdaTwo','lambda2'),('concatName','concat'),('lambdaOrdered','ordered'),('renamedFactory','renamed'),('baseRename','base'),('lambdaRename','renameLambda'),('lambdaPair','pair'),('lambdaAnonymous','anonymous'),('nullBranches','nullBranches'),('referenceBranches','referenceBranches'),('freshIdentity','freshIdentity')]:
  p=compile(method)
  if p.returncode:raise RuntimeError(p.stderr)
  j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver',label,*map(str,vals)],text=True,capture_output=True,check=True,timeout=20)
  r=subprocess.run([str(d/method),*args],text=True,capture_output=True,timeout=20)
  if r.returncode or r.stdout!=j.stdout:raise AssertionError((method,j.stdout,r.stdout,r.stderr))
 for method in ('nameNul','nameSurrogate'):
  p=compile(method)
  if p.returncode:raise RuntimeError(p.stderr)
  r=subprocess.run([str(d/method),'1'],text=True,capture_output=True,timeout=10)
  if r.returncode==0 or 'no se pudo crear pool' not in r.stderr:raise AssertionError(('nombre fuera de perfil',method,r.returncode,r.stderr))
 p=compile('noExplicitName')
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'noExplicitName'),'1'],text=True,capture_output=True,timeout=10)
 if r.returncode==0 or 'nombre predeterminado de worker no soportado' not in r.stderr:raise AssertionError(('nombre predeterminado',r.returncode,r.stderr))
 p=compile('badRenameLambda')
 if p.returncode==0 or 'lambda factory implementación no soportada' not in p.stderr:raise AssertionError(('lambda modificada',p.returncode,p.stderr))
 p=compile('many')
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'many'),'1'],text=True,capture_output=True,timeout=10)
 if r.returncode==0 or 'requiere un worker' not in r.stderr:raise AssertionError((r.returncode,r.stderr))
 p=compile('modeFalse')
 if p.returncode:raise RuntimeError(p.stderr)
 r=subprocess.run([str(d/'modeFalse'),'1'],text=True,capture_output=True,timeout=10)
 if r.returncode==0 or 'async=true' not in r.stderr:raise AssertionError((r.returncode,r.stderr))
 p=compile('badWorker')
 if p.returncode==0 or 'override run/start' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badFactory')
 if p.returncode==0 or 'factory Java no trivial' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badLambdaTwo')
 if p.returncode==0 or 'lambda factory implementación no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badAlt')
 if p.returncode==0 or 'bootstrap factory no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badLambda')
 if p.returncode==0 or 'lambda factory implementación no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badConcat')
 if p.returncode==0 or 'concat firma no soportada' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badNamedWorker')
 if p.returncode==0 or 'objeto requiere clase final' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('badAtomicFactory')
 if p.returncode==0 or 'factory Java no trivial' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=compile('mutableFactory')
 if p.returncode==0 or 'objeto requiere clase final' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 312 resultados Java: factory traducida, constructor de worker, onStart/onTermination, tareas QuartPos, AtomicInteger con referencias capturadas, literales/concatenación UTF-16 y factory lambda con String y AtomicInteger capturados en ambos órdenes, setName/getName, shutdown/awaitTermination por interfaz y cierre sin tareas; guardas de factory, override de worker, modo y paralelismo; lambda y constructor sintéticos cotejados instrucción por instrucción con los oficiales')
