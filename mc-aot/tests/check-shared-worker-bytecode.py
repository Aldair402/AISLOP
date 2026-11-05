#!/usr/bin/env python3
"""Runnable Java AOT acotado en Rayon y el mismo objeto del backend principal.

Este no es un programa Java ForkJoinPool traducido: el scheduling se construye
por el modo experimental y los wrappers Runnable verificados no se materializan.
"""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
final class Cell { int count; Cell(){count=2147483640;} synchronized void increment(){count++;} }
final class IncrementTask implements Runnable {final Cell target; IncrementTask(Cell t){target=t;} public void run(){target.increment();}}
public class WorkerEntry {static Cell shared=new Cell(); public static int tick(int n){shared.increment();return 0;} public static int read(int n){return shared.count;} }
'''
driver='''package net.minecraft.test;
import java.util.concurrent.*;
public class Driver{public static void main(String[]a)throws Exception{
 int n=Integer.parseInt(a[0]);ForkJoinPool pool=new ForkJoinPool(4);CountDownLatch gate=new CountDownLatch(1);ForkJoinTask<?>[] jobs=new ForkJoinTask<?>[4];
 for(int j=0;j<4;j++){Runnable task=new IncrementTask(WorkerEntry.shared);jobs[j]=pool.submit(()->{try{gate.await();for(int k=0;k<n;k++)task.run();}catch(InterruptedException e){throw new AssertionError(e);}});}
 gate.countDown();for(int k=0;k<n;k++)WorkerEntry.tick(0);for(var j:jobs)j.join();pool.shutdown();System.out.println(WorkerEntry.read(0));
}}'''
def run(args,**kw):
 kw.setdefault('timeout',180);return subprocess.run(args,text=True,**kw)
def jar_fixture(d,src,include_driver=False):
 d.mkdir(parents=True,exist_ok=True);(d/'WorkerEntry.java').write_text(src)
 files=[str(d/'WorkerEntry.java')]
 if include_driver:(d/'Driver.java').write_text(driver);files.append(str(d/'Driver.java'))
 p=run([str(jdk/'javac'),'-d',str(d),*files],capture_output=True)
 if p.returncode:raise RuntimeError(('javac',p.stderr))
 p=run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True)
 if p.returncode:raise RuntimeError(('jar',p.stderr))
 return d/'fixture.jar'
def compile(jar,out,field='shared',task='net/minecraft/test/IncrementTask',tick='tick',read='read'):
 return run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','shared-worker-demo',str(jar),'net/minecraft/test/WorkerEntry',field,task,str(out),tick,read],capture_output=True,timeout=180)
with tempfile.TemporaryDirectory(prefix='mc-shared-worker-') as tmp:
 d=pathlib.Path(tmp);good=d/'good';jar=jar_fixture(good,source,True);out=good/'native'
 p=compile(jar,out)
 if p.returncode:raise RuntimeError(('compiler',p.stderr))
 # Cada invocación parte de un heap nuevo. Integer.MAX_VALUE cruza el límite.
 env=os.environ.copy();env['PATH']='/nonexistent';env.pop('JAVA_HOME',None)
 vals=[0,1,2,3,9,100,1000,10000]+[127,512,1000]*8
 for n in vals:
  java=run([str(jdk/'java'),'-cp',str(good),'net.minecraft.test.Driver',str(n)],capture_output=True,timeout=30)
  native=run([str(out),str(n)],capture_output=True,env=env,timeout=30)
  if java.returncode or native.returncode or java.stdout!=native.stdout:raise AssertionError((n,java.stdout,java.stderr,native.stdout,native.stderr))
 ldd=run(['ldd',str(out)],capture_output=True)
 if ldd.returncode or 'libjvm' in ldd.stdout.lower():raise AssertionError(ldd.stdout)
 for args in [[],['-1'],['10001'],['xyz'],['1','2']]:
  p=run([str(out),*args],capture_output=True,env=env,timeout=10)
  if p.returncode==0 or 'repeticiones' not in p.stderr:raise AssertionError((args,p.returncode,p.stderr))
 # Los patrones se comprueban por bytecode/descriptor, no por nombre o hash.
 bads=[
  ('nonfinal-task',source.replace('final class IncrementTask','class IncrementTask'),'clase final'),
  ('nonfinal-target',source.replace('final class Cell','class Cell'),'clase final'),
  ('two-fields',source.replace('int count; Cell()', 'int count; int extra; Cell()'),'único campo int'),
  ('volatile',source.replace('int count; Cell()', 'volatile int count; Cell()'),'no volatile'),
  ('unsynchronized',source.replace('synchronized void increment','void increment'),'synchronized'),
  ('increment-two',source.replace('count++;','count+=2;'),'incremento fuera de perfil'),
  ('extra-run',source.replace('target.increment();}}','target.increment();target.increment();}}'),'bytecode run'),
  ('mutable-capture',source.replace('final Cell target;','Cell target;'),'captura final'),
  ('constructor-side-effect',source.replace('IncrementTask(Cell t){target=t;}','IncrementTask(Cell t){target=t;t.increment();}'),'constructor de captura'),
  ('task-extra-method',source.replace('public void run(){target.increment();}', 'public void run(){target.increment();} public int extra(){return 2;}'),'métodos adicionales en Runnable'),
  ('target-extra-method',source.replace('synchronized void increment(){count++;}', 'synchronized void increment(){count++;} int extra(){return 2;}'),'métodos adicionales en destino'),
  ('extra-constructor',source.replace('IncrementTask(Cell t){target=t;}', 'IncrementTask(Cell t){target=t;} IncrementTask(){target=null;}'),'constructores adicionales'),
  ('task-clinit',source.replace('implements Runnable {final','implements Runnable {static {System.setProperty("x","y");} final'),'<clinit>'),
  ('target-clinit',source.replace('final class Cell { int','final class Cell { static {System.setProperty("x","y");} int'),'<clinit>'),
  ('tick-extra',source.replace('shared.increment();return 0;','shared.increment();shared.increment();return 0;'),'tick fuera de perfil'),
  ('read-extra',source.replace('return shared.count;','return shared.count+1;'),'lectura fuera de perfil'),
 ]
 for name,src,expected in bads:
  j=jar_fixture(d/name,src);dest=d/name/'out';p=compile(j,dest)
  if p.returncode==0 or expected not in p.stderr or dest.exists():raise AssertionError((name,p.returncode,p.stderr))
 p=compile(jar,d/'bad-field','missing')
 if p.returncode==0 or 'campo static' not in p.stderr or (d/'bad-field').exists():raise AssertionError(('bad-field',p.returncode,p.stderr))
 # La clase declarada es válida, pero no existe captura null en el perfil.
 null_src=source.replace('static Cell shared=new Cell();','static Cell shared=null;')
 nulljar=jar_fixture(d/'null',null_src);p=compile(nulljar,d/'null'/'out')
 if p.returncode:raise RuntimeError(('null compile',p.stderr))
 p=run([str(d/'null'/'out'),'1'],capture_output=True,env=env,timeout=10)
 if p.returncode==0 or 'static null o inválido' not in p.stderr:raise AssertionError(('null',p.returncode,p.stderr))
 print(f'OK: {len(vals)} comparaciones Java 25 con Runnable.run y método synchronized traducidos; 4 tareas Rayon + hilo principal, desbordamiento int, sin JVM externa; {len(bads)+2} guardas de clase/captura/bytecode y 5 de CLI; ForkJoinPool Java no traducido')
# Una variante de la tarea invoca bytecode oficial QuartPos.toBlock(1). El
# compilador comprueba su forma pura exacta antes de plegarlo en el worker.
import hashlib,zipfile
inner=root.parent/'downloads/server-26.3-inner.jar'
with tempfile.TemporaryDirectory(prefix='mc-worker-real-quartpos-') as tmp:
 d=pathlib.Path(tmp);src=source.replace('count++;','count+=net.minecraft.core.QuartPos.toBlock(1);')
 (d/'WorkerEntry.java').write_text(src);(d/'Driver.java').write_text(driver)
 p=run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'WorkerEntry.java'),str(d/'Driver.java')],capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr)
 with zipfile.ZipFile(inner) as z:b=z.read('net/minecraft/core/QuartPos.class')
 assert hashlib.sha256(b).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c'
 clazz=d/'net/minecraft/core/QuartPos.class';clazz.parent.mkdir(parents=True,exist_ok=True);clazz.write_bytes(b)
 p=run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr)
 p=compile(d/'fixture.jar',d/'native')
 if p.returncode:raise RuntimeError(p.stderr)
 env=os.environ.copy();env['PATH']='/nonexistent';env.pop('JAVA_HOME',None)
 vals=[0,1,2,3,100,1000,10000]+[50,250,1000]*8
 for n in vals:
  j=run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.Driver',str(n)],capture_output=True,timeout=30)
  a=run([str(d/'native'),str(n)],capture_output=True,env=env,timeout=30)
  if j.returncode or a.returncode or j.stdout!=a.stdout:raise AssertionError((n,j.stdout,j.stderr,a.stdout,a.stderr))
 # Reemplazar únicamente el bytecode de toBlock hace que el guard lo rechace;
 # hay dos copias iguales (fromSection también), y toBlock es la primera.
 old=bytes.fromhex('000000041a0578ac');new=bytes.fromhex('000000041a0478ac');assert b.count(old)==2
 clazz.write_bytes(b.replace(old,new,1));run([str(jdk/'jar'),'cf',str(d/'modified.jar'),'-C',str(d),'net'],capture_output=True)
 p=compile(d/'modified.jar',d/'rejected')
 if p.returncode==0 or 'bytecode QuartPos.toBlock fuera de perfil' not in p.stderr or (d/'rejected').exists():raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} resultados Java/nativo ejecutando Runnable acotado con QuartPos.toBlock oficial; hash verificado y bytecode alterado rechazado; sin certificar clases completas')
