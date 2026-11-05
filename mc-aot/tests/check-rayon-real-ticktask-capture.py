#!/usr/bin/env python3
"""TickTask oficial materializada con Runnable anidado y capturas compartidas, FJP/monitores limitados."""
import os,pathlib,subprocess,tempfile,hashlib
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;import net.minecraft.server.TickTask;
final class Cell {int count;Cell(){count=2147483600;}synchronized void tick(){count+=net.minecraft.core.QuartPos.toBlock(1);}synchronized int read(){return count;}}
final class Work implements Runnable {final Cell cell;Work(Cell c){cell=c;}public void run(){for(int i=0;i<1000;i++)cell.tick();}}
public class CapturedFixture {public static int run(int n){Cell c=new Cell();ForkJoinPool p=new ForkJoinPool(4);TickTask ta=new TickTask(23,new Work(c));ForkJoinTask<?> a=p.submit(ta);ForkJoinTask<?> b=p.submit(new TickTask(7,new Work(c)));ForkJoinTask<?> d=p.submit(new TickTask(11,new Work(c)));ForkJoinTask<?> e=p.submit(new TickTask(15,new Work(c)));for(int i=0;i<n;i++)c.tick();a.join();b.join();d.join();e.join();p.shutdown();return c.read()+ta.getTick();}}
'''
driver='''import net.minecraft.test.CapturedFixture;public class Driver {public static void main(String[] args){for(String a:args)System.out.println(CapturedFixture.run(Integer.parseInt(a)));}}'''
def r(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def check(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-rayon-captured-') as t:
 d=pathlib.Path(t);inner=root.parent/'downloads/server-26.3-inner.jar';(d/'CapturedFixture.java').write_text(source);(d/'Driver.java').write_text(driver)
 check(r([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'CapturedFixture.java'),str(d/'Driver.java')],capture_output=True))
 import zipfile
 with zipfile.ZipFile(inner) as z:
  for name,digest in [('net/minecraft/core/QuartPos.class','0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c'),('net/minecraft/server/TickTask.class','dae918ab7da617b85384411773b9759ffbc0c0609bfc06c7dc4af85b76fa69b6')]:
   p=d/name;p.parent.mkdir(parents=True,exist_ok=True);b=z.read(name);assert hashlib.sha256(b).hexdigest()==digest;p.write_bytes(b)
 check(r([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True))
 env=os.environ.copy();env['MC_AOT_RAYON_PROJECT_REFERENCES']='1'
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/CapturedFixture',str(d/'native'),'run','(I)I']
 p=r(cmd,capture_output=True,env=env);check(p)
 vals=[0,1,2,3,10,100,1000]*4
 java=check(r([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,vals)],capture_output=True,timeout=60))
 args=[]
 for x in vals:args.extend([str(x),'--phase'])
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 native=check(r([str(d/'native'),*args],capture_output=True,timeout=60,env=native_env))
 assert java.stdout==native.stdout,(java.stdout,native.stdout,native.stderr)
 env.pop('MC_AOT_RAYON_PROJECT_REFERENCES');bad=r(cmd[:-3]+[str(d/'bad'),'run','(I)I'],capture_output=True,env=env)
 assert bad.returncode!=0 and not (d/'bad').exists(),bad.stderr
 # Cada caso se vuelve a compilar y se rechaza antes de generar ejecutable.
 env['MC_AOT_RAYON_PROJECT_REFERENCES']='1'
 cases=[('nonfinal-target',source.replace('final class Cell','class Cell'),'objeto requiere clase final'),
        ('target-interface',source.replace('final class Cell {','final class Cell implements java.io.Serializable {'),'objeto requiere clase final'),
        ('target-clinit',source.replace('final class Cell {','final class Cell {static int nope=1;'),'objeto requiere clase final'),
        ('mutable-capture',source.replace('final Cell cell;','Cell cell;'),'captura de referencia debe ser final')]
 for label,changed,guard in cases:
  c=d/label;c.mkdir();(c/'CapturedFixture.java').write_text(changed)
  check(r([str(jdk/'javac'),'-cp',str(inner),'-d',str(c),str(c/'CapturedFixture.java')],capture_output=True))
  import shutil
  for file in ['net/minecraft/core/QuartPos.class','net/minecraft/server/TickTask.class']:
   dest=c/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(d/file,dest)
  check(r([str(jdk/'jar'),'cf',str(c/'bad.jar'),'-C',str(c),'net'],capture_output=True))
  failure=r(cmd[:7]+[str(c/'bad.jar'),'net/minecraft/test/CapturedFixture',str(c/'rejected'),'run','(I)I'],capture_output=True,env=env)
  assert failure.returncode!=0 and guard in failure.stderr and not (c/'rejected').exists(),(label,failure.stderr)
 # Hash conservador protege la excepción que permite TickTask no final.
 altered=d/'net/minecraft/server/TickTask.class';original=altered.read_bytes();b=original.replace(b'TickTask.java',b'XickTask.java');assert b!=original;altered.write_bytes(b)
 check(r([str(jdk/'jar'),'cf',str(d/'altered.jar'),'-C',str(d),'net'],capture_output=True));failure=r(cmd[:7]+[str(d/'altered.jar'),'net/minecraft/test/CapturedFixture',str(d/'bad-hash'),'run','(I)I'],capture_output=True,env=env)
 assert failure.returncode!=0 and 'TickTask: versión de clase no verificada' in failure.stderr and not (d/'bad-hash').exists(),failure.stderr
 print(f'OK: {len(vals)} resultados Java/ForkJoinPool frente a Rayon con TickTask.run/getTick y QuartPos oficiales; TickTask y Runnable anidado materializados, cuatro capturas comparten objeto, monitores, overflow y 6 guardas; backend concurrente aislado')
