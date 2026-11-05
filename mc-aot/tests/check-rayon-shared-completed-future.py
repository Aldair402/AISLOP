#!/usr/bin/env python3
"""Un completedFuture normal es compartido por bytecode Java entre workers Rayon."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;
final class Work implements Runnable {
 final CompletableFuture<Object> future;
 Work(CompletableFuture<Object> future){this.future=future;}
 public void run(){for(int i=0;i<100;i++)if(future.join()=="marker")FutureSharedFixture.tick();}
}
public class FutureSharedFixture {
 static volatile int total;
 public static synchronized void tick(){total++;}
 public static int run(int n) {
  CompletableFuture<Object> f=CompletableFuture.completedFuture("marker");
  ForkJoinPool p=new ForkJoinPool(4);
  ForkJoinTask<?> a=p.submit(new Work(f)),b=p.submit(new Work(f)),c=p.submit(new Work(f)),d=p.submit(new Work(f));
  for(int i=0;i<n;i++)if(f.getNow(null)=="marker")tick();
  a.join();b.join();c.join();d.join();p.shutdown();return total;
 }
}'''
driver='''import net.minecraft.test.FutureSharedFixture;public class Driver{public static void main(String[] args){for(String a:args)System.out.println(FutureSharedFixture.run(Integer.parseInt(a)));}}'''
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def ok(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-shared-future-') as tmp:
 d=pathlib.Path(tmp);(d/'FutureSharedFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 ok(run([str(jdk/'javac'),'-d',str(d),str(d/'FutureSharedFixture.java'),str(d/'Driver.java')],capture_output=True))
 ok(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 env=os.environ.copy();env['MC_AOT_RAYON_COMPLETED_FUTURE']='1'
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/FutureSharedFixture',str(d/'native'),'run','(I)I']
 ok(run(cmd,capture_output=True,env=env))
 values=[0,1,2,10,200]*4
 java=ok(run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,values)],capture_output=True))
 args=[]
 for n in values:args.extend([str(n),'--phase'])
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 native=ok(run([str(d/'native'),*args],capture_output=True,env=native_env))
 assert java.stdout==native.stdout,(java.stdout,native.stdout,native.stderr)
 changed=source.replace('final CompletableFuture<Object> future;', 'CompletableFuture<Object> future;')
 c=d/'bad';c.mkdir();(c/'FutureSharedFixture.java').write_text(changed)
 ok(run([str(jdk/'javac'),'-d',str(c),str(c/'FutureSharedFixture.java')],capture_output=True))
 ok(run([str(jdk/'jar'),'cf',str(c/'bad.jar'),'-C',str(c),'net'],capture_output=True))
 bad=run(cmd[:7]+[str(c/'bad.jar'),'net/minecraft/test/FutureSharedFixture',str(c/'native'),'run','(I)I'],capture_output=True,env=env)
 assert bad.returncode!=0 and 'captura CompletableFuture debe ser final' in bad.stderr and not (c/'native').exists(),bad.stderr
 print(f'OK: {len(values)} rondas Java/Rayon, cuatro Runnable capturan el mismo completedFuture normal; join/getNow, monitor estático y guarda de captura final; bytecode sintético, backend aislado')
