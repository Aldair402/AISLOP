#!/usr/bin/env python3
"""Solo completedFuture normal: identidad/null, consultas y rechazos; no future general."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.CompletableFuture;
public final class FutureFixture {
 public static int run(int n) throws Exception {
  Object marker="marker", other="other";
  CompletableFuture<Object> a=CompletableFuture.completedFuture(marker);
  CompletableFuture<Object> b=CompletableFuture.completedFuture(marker);
  CompletableFuture<Object> nil=CompletableFuture.completedFuture(null);
  int r=net.minecraft.core.QuartPos.toBlock(n);
  if(a!=b)r+=1;
  if(a.join()==marker)r+=2;
  if(a.get()==b.get())r+=4;
  if(a.getNow(other)==marker)r+=8;
  if(nil.join()==null && nil.get()==null && nil.getNow(other)==null)r+=16;
  if(a.isDone() && nil.isDone())r+=32;
  if(!a.isCancelled() && !a.isCompletedExceptionally())r+=64;
  if(!a.complete(other) && a.join()==marker)r=r+128;
  if(!nil.complete(marker) && nil.join()==null)r=r+256;
  if(!a.cancel(true) && !nil.cancel(false))r=r+512;
  if(!a.isCancelled() && a.join()==marker)r=r+1024;
  return r;
 }
}'''
driver='''import net.minecraft.test.FutureFixture;public class Driver {public static void main(String[] args) throws Exception {for(String a:args)System.out.println(FutureFixture.run(Integer.parseInt(a)));}}'''
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def ok(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-completed-future-') as t:
 d=pathlib.Path(t); inner=root.parent/'downloads/server-26.3-inner.jar';(d/'FutureFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 ok(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'FutureFixture.java'),str(d/'Driver.java')],capture_output=True))
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';data=z.read(name);assert hashlib.sha256(data).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c';p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 ok(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 env=os.environ.copy();env['MC_AOT_RAYON_COMPLETED_FUTURE']='1'
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/FutureFixture',str(d/'native'),'run','(I)I']
 ok(run(cmd,env=env,capture_output=True))
 values=[-2147483648,-536870912,-1,0,1,3,255,536870911,2147483647]*10
 java=ok(run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,values)],capture_output=True))
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 native=ok(run([str(d/'native'),*map(str,values)],capture_output=True,env=native_env))
 assert java.stdout==native.stdout,(java.stdout,native.stdout,native.stderr)
 disabled=env.copy();disabled.pop('MC_AOT_RAYON_COMPLETED_FUTURE')
 bad=run(cmd[:9]+[str(d/'disabled'),'run','(I)I'],capture_output=True,env=disabled)
 assert bad.returncode!=0 and 'requiere MC_AOT_RAYON_COMPLETED_FUTURE' in bad.stderr and not (d/'disabled').exists(),bad.stderr
 # Q-AB-3: `completed-only` (el valor de A) se honra, no se reinterpreta: este
 # perfil de futuro completado compila igual solo con ese valor.
 solo_completado=env.copy();solo_completado.pop('MC_AOT_RAYON_COMPLETED_FUTURE')
 solo_completado['MC_AOT_FUTURES']='completed-only'
 ok(run(cmd[:9]+[str(d/'solo-completado'),'run','(I)I'],capture_output=True,env=solo_completado))
 nativo_solo=ok(run([str(d/'solo-completado'),*map(str,values)],capture_output=True,env=native_env))
 assert java.stdout==nativo_solo.stdout,('completed-only',java.stdout[:200],nativo_solo.stdout[:200])
 # El futuro pendiente ya esta soportado y se verifica en check-rayon-pending-future.py.
 cases=[('obtrude','CompletableFuture.completedFuture((Object)null).obtrudeValue(null)','operación no soportada: obtrudeValue'),
        ('exception','CompletableFuture.completedFuture((Object)null).completeExceptionally(null)','operación no soportada: completeExceptionally')]
 for label,expr,error in cases:
  c=d/label;c.mkdir();(c/'FutureFixture.java').write_text('package net.minecraft.test;import java.util.concurrent.*;public class FutureFixture {public static int run(int n){'+expr+';return n;}}')
  ok(run([str(jdk/'javac'),'-d',str(c),str(c/'FutureFixture.java')],capture_output=True))
  ok(run([str(jdk/'jar'),'cf',str(c/'bad.jar'),'-C',str(c),'net'],capture_output=True))
  cmd_bad=cmd[:7]+[str(c/'bad.jar'),'net/minecraft/test/FutureFixture',str(c/'native'),'run','(I)I']
  bad=run(cmd_bad,capture_output=True,env=env)
  assert bad.returncode!=0 and error in bad.stderr and not (c/'native').exists(),(label,bad.stderr)
 print(f'OK: {len(values)} resultados Java 25/Rayon con el alias historico y con MC_AOT_FUTURES=completed-only; completedFuture normal, get/join/getNow, identidad/null, estados, complete/cancel ya completado, QuartPos oficial y cuatro guardas; backend concurrente aislado, sin future general')
