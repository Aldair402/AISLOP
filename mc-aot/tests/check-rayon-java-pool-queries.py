#!/usr/bin/env python3
"""Consultas de lifecycle (isShutdown/isTerminated/getParallelism) en bytecode Java
sobre Rayon: no implementan ForkJoinPool completo ni excepciones Java."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;import net.minecraft.core.QuartPos;
public class PoolQueryFixture {
 static volatile int total;static volatile int done;
 public static synchronized void add(int n){total=total+n;done=done+1;}
 public static void waitDone(int n){while(done<n){}}
 public static int run(int n) throws Exception{
  ForkJoinPool p=new ForkJoinPool(3);
  int r=0;
  if(!p.isShutdown())r=r+1;
  if(!p.isTerminated())r=r+2;
  r=r+p.getParallelism()*4;
  p.submit(new Work(n)).join();
  if(!p.isShutdown())r=r+64;
  if(!p.isTerminated())r=r+128;
  p.shutdown();
  if(p.isShutdown())r=r+256;
  if(p.awaitTermination(5,TimeUnit.SECONDS))r=r+512;
  if(p.isTerminated())r=r+1024;
  r=r+p.getParallelism()*2048;
  return r+total;
 }
 public static int unused(int n) throws Exception{
  ForkJoinPool p=new ForkJoinPool(2);
  int r=0;
  if(!p.isShutdown())r=r+1;
  if(!p.isTerminated())r=r+2;
  r=r+p.getParallelism()*4;
  p.shutdown();
  if(p.isShutdown())r=r+16;
  if(p.awaitTermination(5,TimeUnit.SECONDS))r=r+32;
  if(p.isTerminated())r=r+64;
  return r+n;
 }
 public static int service(int n) throws Exception{
  ForkJoinPool p=new ForkJoinPool(1);
  ExecutorService e=p;
  int r=0;
  if(!e.isShutdown())r=r+1;
  if(!e.isTerminated())r=r+2;
  e.execute(new Work(n));
  p.submit(new WaitDone(1)).join();
  if(!e.isShutdown())r=r+8;
  e.shutdown();
  if(e.isShutdown())r=r+16;
  if(e.awaitTermination(5,TimeUnit.SECONDS))r=r+32;
  if(e.isTerminated())r=r+64;
  return r+total;
 }
}
final class Work implements Runnable {final int n;Work(int n){this.n=n;}public void run(){PoolQueryFixture.add(QuartPos.toBlock(n));}}
final class WaitDone implements Runnable {final int n;WaitDone(int n){this.n=n;}public void run(){PoolQueryFixture.waitDone(n);}}
'''
driver='''import net.minecraft.test.PoolQueryFixture;public class Driver{public static void main(String[]a) throws Exception{String m=a[0];for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(m.equals("unused")?PoolQueryFixture.unused(n):m.equals("service")?PoolQueryFixture.service(n):PoolQueryFixture.run(n));}}}'''
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def ok(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-pool-queries-') as temp:
 d=pathlib.Path(temp);(d/'PoolQueryFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 inner=root.parent/'downloads/server-26.3-inner.jar'
 if not inner.exists():raise SystemExit(f'FALTA el bundle oficial en {inner}; ver Preparación tras clonar del README')
 ok(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'PoolQueryFixture.java'),str(d/'Driver.java')],capture_output=True))
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';data=z.read(name)
  assert hashlib.sha256(data).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c',hashlib.sha256(data).hexdigest()
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 ok(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 def compile(method,out):
  return run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/PoolQueryFixture',str(out),method,'(I)I'],capture_output=True)
 vals=[0,1,-1,3,42,100,-2147483648,2147483647]
 native_env=os.environ.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 total=0
 for method in ('run','unused','service'):
  p=compile(method,d/method)
  if p.returncode:raise RuntimeError(('compilación',method,p.stderr))
  j=ok(run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver',method,*map(str,vals)],capture_output=True))
  args=[]
  for v in vals:args.extend([str(v),'--phase'])
  r=ok(run([str(d/method),*args],capture_output=True,env=native_env))
  if j.stdout!=r.stdout:raise AssertionError((method,j.stdout,r.stdout,r.stderr))
  total+=len(vals)
 # guardas: el perfil no promete consultas fuera de los métodos traducidos
 bad=d/'bad';bad.mkdir();(bad/'PoolQueryFixture.java').write_text(source.replace('r=r+p.getParallelism()*4;','r=r+p.getActiveThreadCount();'))
 ok(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(bad),str(bad/'PoolQueryFixture.java')],capture_output=True))
 ok(run([str(jdk/'jar'),'cf',str(bad/'bad.jar'),'-C',str(bad),'net'],capture_output=True))
 p=run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(bad/'bad.jar'),'net/minecraft/test/PoolQueryFixture',str(bad/'native'),'run','(I)I'],capture_output=True)
 if p.returncode==0:raise AssertionError('getActiveThreadCount no debe aceptarse')
 # Sin guarda dedicada: cae en el rechazo de carga de la clase JDK. Se documenta
 # como rechazo de traducción, no como equivalencia ni como mensaje específico.
 if 'clase no encontrada' not in p.stderr and 'llamada externa no soportada' not in p.stderr:raise AssertionError(('guarda getActiveThreadCount',p.stderr))
 if (bad/'native').exists():raise AssertionError('no debe generarse binario tras un rechazo')
 print(f'OK: {total} resultados Java 25/Rayon para isShutdown, isTerminated y getParallelism antes y después de submit, shutdown y awaitTermination, incluidos un pool nunca usado y el despacho por interfaz ExecutorService, con QuartPos oficial; guarda de getActiveThreadCount (rechazo de traducción, sin guarda propia) y sin binario tras el rechazo; backend concurrente aislado, sin ForkJoinPool completo')
