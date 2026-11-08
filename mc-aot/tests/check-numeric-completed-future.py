#!/usr/bin/env python3
"""completedFuture normal en el backend principal monohilo, no futuro general."""
import ast,hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
# Reutiliza el fixture textual del diferencial del backend concurrente, sin ejecutar su script.
tree=ast.parse((root/'tests/check-rayon-completed-future.py').read_text())
source=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='source' for t in node.targets))
source=source.replace('  return r;','''  Object obj=a;
  if(obj instanceof CompletableFuture && !(other instanceof CompletableFuture) && ((CompletableFuture<?>)obj).join()==marker)r=r+2048;
  if(a.getClass().getName().equals("java.util.concurrent.CompletableFuture"))r=r+4096;
  try { CompletableFuture<Object> bad=null; bad.get(); } catch(NullPointerException expected) { r=r+8192; }
  return r;''')
driver='''import net.minecraft.test.FutureFixture;public class Driver {public static void main(String[] args) throws Exception {for(String a:args)System.out.println(FutureFixture.run(Integer.parseInt(a)));}}'''
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def ok(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-numeric-completed-future-') as t:
 d=pathlib.Path(t);inner=root.parent/'downloads/server-26.3-inner.jar';(d/'FutureFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 ok(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'FutureFixture.java'),str(d/'Driver.java')],capture_output=True))
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';data=z.read(name);assert hashlib.sha256(data).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c';p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 ok(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 env=os.environ.copy();env['MC_AOT_NUMERIC_COMPLETED_FUTURE']='1'
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FutureFixture',str(d/'native'),'run','(I)I']
 ok(run(cmd,env=env,capture_output=True))
 values=[-2147483648,-536870912,-1,0,1,3,255,536870911,2147483647]*10
 java=ok(run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,values)],capture_output=True))
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 native=ok(run([str(d/'native'),*[v for n in values for v in ('0',str(n))]],capture_output=True,env=native_env))
 assert java.stdout==native.stdout,(java.stdout,native.stdout,native.stderr)
 disabled=env.copy();disabled.pop('MC_AOT_NUMERIC_COMPLETED_FUTURE')
 bad=run(cmd[:9]+[str(d/'disabled'),'run','(I)I'],capture_output=True,env=disabled)
 assert bad.returncode!=0 and 'MC_AOT_FUTURES=completed-only' in bad.stderr and not (d/'disabled').exists(),bad.stderr
 # Q-AC-7/Q-AC-9: el nombre unificado canónico basta por sí solo y da el mismo binario observable.
 unified=disabled.copy();unified['MC_AOT_FUTURES']='restricted'
 ok(run(cmd[:9]+[str(d/'restricted'),'run','(I)I'],capture_output=True,env=unified))
 native_restricted=ok(run([str(d/'restricted'),*[v for n in values for v in ('0',str(n))]],capture_output=True,env=native_env))
 assert native_restricted.stdout==java.stdout,(native_restricted.stdout,java.stdout)
 # `completed-only` se conserva como alias histórico del mismo perfil por una versión.
 legacy=disabled.copy();legacy['MC_AOT_FUTURES']='completed-only'
 ok(run(cmd[:9]+[str(d/'legacy'),'run','(I)I'],capture_output=True,env=legacy))
 native_legacy=ok(run([str(d/'legacy'),*[v for n in values for v in ('0',str(n))]],capture_output=True,env=native_env))
 assert native_legacy.stdout==java.stdout,(native_legacy.stdout,java.stdout)
 # `off` apaga el perfil explícitamente, igual que en el backend concurrente.
 off=disabled.copy();off['MC_AOT_FUTURES']='off'
 bad=run(cmd[:9]+[str(d/'off'),'run','(I)I'],capture_output=True,env=off)
 assert bad.returncode!=0 and 'MC_AOT_FUTURES=restricted' in bad.stderr and not (d/'off').exists(),bad.stderr
 # Un valor desconocido se rechaza, no se ignora en silencio.
 bogus=disabled.copy();bogus['MC_AOT_FUTURES']='completed'
 bad=run(cmd[:9]+[str(d/'bogus'),'run','(I)I'],capture_output=True,env=bogus)
 assert bad.returncode!=0 and 'MC_AOT_FUTURES: valor no soportado: completed' in bad.stderr and not (d/'bogus').exists(),bad.stderr
 cases=[('pending','new CompletableFuture<Object>().isDone()','new no soportado: java/util/concurrent/CompletableFuture'),
        ('obtrude','CompletableFuture.completedFuture((Object)null).obtrudeValue(null)','operación no soportada: obtrudeValue'),
        ('exception','CompletableFuture.completedFuture((Object)null).completeExceptionally(null)','operación no soportada: completeExceptionally')]
 for label,expr,error in cases:
  c=d/label;c.mkdir();(c/'FutureFixture.java').write_text('package net.minecraft.test;import java.util.concurrent.*;public class FutureFixture {public static int run(int n){'+expr+';return n;}}')
  ok(run([str(jdk/'javac'),'-d',str(c),str(c/'FutureFixture.java')],capture_output=True))
  ok(run([str(jdk/'jar'),'cf',str(c/'bad.jar'),'-C',str(c),'net'],capture_output=True))
  bad=run(cmd[:7]+[str(c/'bad.jar'),'net/minecraft/test/FutureFixture',str(c/'native'),'run','(I)I'],capture_output=True,env=env)
  assert bad.returncode!=0 and error in bad.stderr and not (c/'native').exists(),(label,bad.stderr)
 print(f'OK: {len(values)} resultados Java 25/nativo; completedFuture normal monohilo, identidad/null, consultas, complete/cancel ya completado, instanceof/getClass y NPE capturada, QuartPos oficial, cuatro guardas y el opt-in unificado `MC_AOT_FUTURES=restricted` como canónico (`completed-only` como alias histórico, `off` explícito, nombre viejo como alias y valor desconocido rechazado); sin future general ni integración concurrente')
