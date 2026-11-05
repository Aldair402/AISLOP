#!/usr/bin/env python3
"""Futuro PENDIENTE con completado normal en bytecode Java sobre Rayon.
Sin estado fallido ni cancelado, sin callbacks, sin esperas bloqueantes."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;
final class Holder {
 final CompletableFuture<Object> future;
 Holder(CompletableFuture<Object> future){this.future=future;}
}
public class PendingFixture {
 public static int run(int n) {
  CompletableFuture<Object> f=new CompletableFuture<>();
  int r=0;
  if(!f.isDone())r=r+1;
  if(!f.isCancelled())r=r+2;
  if(!f.isCompletedExceptionally())r=r+4;
  if(f.getNow("def")=="def")r=r+8;
  if(f.complete("v"))r=r+16;
  if(!f.complete("w"))r=r+32;
  if(f.isDone())r=r+64;
  if(f.join()=="v")r=r+128;
  if(f.getNow("x")=="v")r=r+256;
  CompletableFuture<Object> nil=new CompletableFuture<>();
  if(nil.complete(null))r=r+512;
  if(nil.join()==null)r=r+1024;
  return r+n;
 }
 public static int pub(int n) {
  CompletableFuture<Object> f=new CompletableFuture<>();
  Holder h=new Holder(f);
  int r=0;
  if(!h.future.isDone())r=r+1;
  if(h.future.complete("v"))r=r+2;
  if(h.future.join()=="v")r=r+4;
  if(h.future.getNow(null)=="v")r=r+8;
  if(!h.future.complete("z"))r=r+16;
  return r+n;
 }
}
'''
driver='''import net.minecraft.test.PendingFixture;public class Driver {public static void main(String[] args) {for(String a:args)System.out.println(PendingFixture.run(Integer.parseInt(a)));}}'''
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def ok(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-pending-future-') as t:
 d=pathlib.Path(t);inner=root.parent/'downloads/server-26.3-inner.jar'
 (d/'PendingFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 ok(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'PendingFixture.java'),str(d/'Driver.java')],capture_output=True))
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';data=z.read(name)
  assert hashlib.sha256(data).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c'
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 ok(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 env=os.environ.copy();env['MC_AOT_RAYON_COMPLETED_FUTURE']='1'
 def compile_cmd(fixture,out,method):
  return ['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(fixture),'net/minecraft/test/PendingFixture',str(out),method,'(I)I']
 values=[-2147483648,-536870912,-1,0,1,3,255,2147483647]*3
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 total=0
 for method in ('run','pub'):
  ok(run(compile_cmd(d/'fixture.jar',d/method,method),capture_output=True,env=env))
  java=ok(run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,values)],capture_output=True))
  if method=='pub':
   # Driver solo ejercita run: usar un driver propio para pub
   (d/'PubDriver.java').write_text('import net.minecraft.test.PendingFixture;public class PubDriver {public static void main(String[] a){for(String x:a)System.out.println(PendingFixture.pub(Integer.parseInt(x)));}}')
   ok(run([str(jdk/'javac'),'-cp',str(d)+os.pathsep+str(inner),'-d',str(d),str(d/'PubDriver.java')],capture_output=True))
   java=ok(run([str(jdk/'java'),'-cp',str(d),'PubDriver',*map(str,values)],capture_output=True))
  native=ok(run([str(d/method),*map(str,values)],capture_output=True,env=native_env))
  if java.stdout!=native.stdout:raise AssertionError((method,java.stdout,native.stdout,native.stderr))
  total+=len(values)
 # Guardas de traduccion: la operacion no existe en el perfil y no se genera binario.
 guardas=[('obtrude','new CompletableFuture<Object>().obtrudeValue(null);return n;','operación no soportada: obtrudeValue'),
          ('excepcional','if(new CompletableFuture<Object>().completeExceptionally(null))return n+1;return n;','operación no soportada: completeExceptionally')]
 for label,expr,error in guardas:
  c=d/label;c.mkdir();(c/'PendingFixture.java').write_text('package net.minecraft.test;import java.util.concurrent.*;public class PendingFixture {public static int run(int n){'+expr+'}}')
  ok(run([str(jdk/'javac'),'-d',str(c),str(c/'PendingFixture.java')],capture_output=True))
  ok(run([str(jdk/'jar'),'cf',str(c/'bad.jar'),'-C',str(c),'net'],capture_output=True))
  bad=run(compile_cmd(c/'bad.jar',c/'native','run'),capture_output=True,env=env)
  if bad.returncode==0 or error not in bad.stderr or (c/'native').exists():
   raise AssertionError((label,bad.returncode,bad.stderr))
 # Guardas de ejecucion: se traducen, pero el binario aborta con diagnostico porque
 # esperar un futuro pendiente o cancelarlo no esta modelado.
 runtime_guardas=[('join-pendiente','Object o=new CompletableFuture<Object>().join();return n+(o==null?1:0);','join de futuro pendiente no soportado'),
                  ('cancel-pendiente-false','if(new CompletableFuture<Object>().cancel(false))return n+1;return n;','cancel de futuro pendiente no soportado'),
                  ('cancel-pendiente-true','if(new CompletableFuture<Object>().cancel(true))return n+1;return n;','cancel de futuro pendiente no soportado')]
 for label,expr,error in runtime_guardas:
  c=d/label;c.mkdir();(c/'PendingFixture.java').write_text('package net.minecraft.test;import java.util.concurrent.*;public class PendingFixture {public static int run(int n){'+expr+'}}')
  ok(run([str(jdk/'javac'),'-d',str(c),str(c/'PendingFixture.java')],capture_output=True))
  ok(run([str(jdk/'jar'),'cf',str(c/'bad.jar'),'-C',str(c),'net'],capture_output=True))
  compiled=run(compile_cmd(c/'bad.jar',c/'native','run'),capture_output=True,env=env)
  if compiled.returncode!=0:raise AssertionError((label,'compilacion inesperada',compiled.stderr))
  ejecutado=run([str(c/'native'),'7'],capture_output=True,env=native_env)
  if ejecutado.returncode==0 or error not in ejecutado.stderr:
   raise AssertionError((label,ejecutado.returncode,ejecutado.stderr))
 # Oracion de cancelacion: se compila el oraculo real del repo (no una copia
 # incrustada) y se comparan sus lineas con lo medido en este JDK.
 opath=pathlib.Path(__file__).with_name('CompletableFutureCancelOracle.java')
 (d/'CompletableFutureCancelOracle.java').write_bytes(opath.read_bytes())
 ok(run([str(jdk/'javac'),'-d',str(d),str(d/'CompletableFutureCancelOracle.java')],capture_output=True))
 medido=ok(run([str(jdk/'java'),'-cp',str(d),'CompletableFutureCancelOracle'],capture_output=True)).stdout.strip().splitlines()
 esperado=['cancel(false): cancelTrue=40/40 isDone=40/40 isCancelled=40/40 isCompletedExceptionally=40/40 getCancellation=40/40 joinCancellation=40/40 getNowCancellation=40/40 completeAfterFalse=40/40',
           'cancel(true): cancelTrue=40/40 isDone=40/40 isCancelled=40/40 isCompletedExceptionally=40/40 getCancellation=40/40 joinCancellation=40/40 getNowCancellation=40/40 completeAfterFalse=40/40',
           'cancel(true) sobre completado devuelve false=40/40']
 if medido!=esperado:raise AssertionError(('oraculo de cancelacion',medido,esperado))
 cancel_results=len(medido)
 # Opt-in obligatorio: sin la variable no hay traduccion de futuros.
 disabled=env.copy();disabled.pop('MC_AOT_RAYON_COMPLETED_FUTURE')
 bad=run(compile_cmd(d/'fixture.jar',d/'disabled','run'),capture_output=True,env=disabled)
 if bad.returncode==0 or 'requiere MC_AOT_RAYON_COMPLETED_FUTURE' not in bad.stderr or (d/'disabled').exists():
  raise AssertionError(('opt-in',bad.stderr))
 print(f'OK: {total} resultados Java 25/Rayon + {cancel_results} lineas del oraculo de cancelacion; futuro pendiente con isDone/isCancelled/isCompletedExceptionally/getNow antes de completar, complete único (true y luego false), join y getNow después, null completado, publicación en campo final de otra clase y QuartPos oficial; guardas de traduccion (obtrudeValue, completeExceptionally), guardas de ejecucion (join y cancel(false)/cancel(true) con futuro pendiente) y opt-in obligatorio; sin espera bloqueante, sin estado fallido/cancelado ni callbacks')
