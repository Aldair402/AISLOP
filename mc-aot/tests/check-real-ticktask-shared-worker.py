#!/usr/bin/env python3
"""TickTask.run oficial -> Runnable acotado -> objeto numérico en Rayon.

Solo se traduce el reenvío de run; no se materializan TickTask, su tick o
constructor, no se traducen getTick, las colas, el despacho dinámico ni el pool Java.
"""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';project=root.parent
source='''package net.minecraft.test;
final class Cell {int count;Cell(){count=2147483640;} synchronized void increment(){count+=net.minecraft.core.QuartPos.toBlock(1);}}
final class IncrementTask implements Runnable {final Cell target;IncrementTask(Cell t){target=t;}public void run(){target.increment();}}
public class WorkerEntry {static Cell shared=new Cell();public static int tick(int n){shared.increment();return 0;}public static int read(int n){return shared.count;}public static Runnable task(){return new IncrementTask(shared);}}
'''
driver='''package net.minecraft.util;
import java.util.concurrent.*;import net.minecraft.test.WorkerEntry;
public class Driver {public static void main(String[]a)throws Exception{int n=Integer.parseInt(a[0]);ForkJoinPool p=new ForkJoinPool(4);CountDownLatch gate=new CountDownLatch(1);ForkJoinTask<?>[] jobs=new ForkJoinTask<?>[4];for(int i=0;i<4;i++){Runnable task=new net.minecraft.server.TickTask(23,WorkerEntry.task());jobs[i]=p.submit(()->{try{gate.await();for(int j=0;j<n;j++)task.run();}catch(InterruptedException e){throw new AssertionError(e);}});}gate.countDown();for(int i=0;i<n;i++)WorkerEntry.tick(0);for(var j:jobs)j.join();p.shutdown();System.out.println(WorkerEntry.read(0));}}
'''
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def check(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-real-ticktask-worker-') as t:
 d=pathlib.Path(t);inner=project/'downloads/server-26.3-inner.jar'
 for n,s in [('WorkerEntry.java',source),('Driver.java',driver)]:(d/n).write_text(s)
 check(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'WorkerEntry.java'),str(d/'Driver.java')],capture_output=True))
 with zipfile.ZipFile(inner) as z:
  files={'net/minecraft/server/TickTask.class':'dae918ab7da617b85384411773b9759ffbc0c0609bfc06c7dc4af85b76fa69b6','net/minecraft/core/QuartPos.class':'0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c'}
  for name,digest in files.items():
   b=z.read(name);assert hashlib.sha256(b).hexdigest()==digest
   p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
   if name.endswith('TickTask.class'):official=b
 check(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 def compile(jar,out,flag='--ticktask-wrapper'):
  return run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','shared-worker-demo',str(jar),'net/minecraft/test/WorkerEntry','shared','net/minecraft/test/IncrementTask',str(out),'tick','read',flag],capture_output=True,timeout=180)
 p=compile(d/'fixture.jar',d/'native');check(p)
 assert 'fn ticktask_run_aot' in (d/'native.rs').read_text()
 env=os.environ.copy();env['PATH']='/nonexistent';env.pop('JAVA_HOME',None)
 vals=[0,1,2,3,100,1000,10000]+[64,512,1000]*8
 for n in vals:
  j=run([str(jdk/'java'),'-cp',str(d),'net.minecraft.util.Driver',str(n)],capture_output=True,timeout=30)
  a=run([str(d/'native'),str(n)],capture_output=True,timeout=30,env=env)
  if j.returncode or a.returncode or j.stdout!=a.stdout:raise AssertionError((n,j.stdout,j.stderr,a.stdout,a.stderr))
 # Cualquier cambio al wrapper oficial se rechaza antes de emitir un binario.
 p=d/'net/minecraft/server/TickTask.class';altered=official.replace(b'TickTask.java',b'XickTask.java');assert altered!=official;p.write_bytes(altered)
 check(run([str(jdk/'jar'),'cf',str(d/'bad.jar'),'-C',str(d),'net'],capture_output=True));bad=compile(d/'bad.jar',d/'rejected')
 assert bad.returncode!=0 and 'TickTask versión no verificada' in bad.stderr and not (d/'rejected').exists(),bad.stderr
 # Esta opción es explícita y no acepta nombres alternativos.
 bad=compile(d/'fixture.jar',d/'badflag','--other-wrapper')
 assert bad.returncode!=0 and 'uso: mc-aot shared-worker-demo' in bad.stderr and not (d/'badflag').exists(),bad.stderr
 print(f'OK: {len(vals)} resultados Java/nativo con TickTask.run y QuartPos.toBlock oficiales; hashes, wrapper modificado y flag inválido; solo forwarding, sin getTick, colas, despacho dinámico ni pool Java')
