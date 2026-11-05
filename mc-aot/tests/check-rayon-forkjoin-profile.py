#!/usr/bin/env python3
"""Contraste de propiedades acotadas con un ForkJoinPool Java 25 real.
Contrasta contadores de hooks Rust con un worker Java; no ejecuta callbacks Java traducidos ni comprueba interrupciones o JFR.
"""
import os, pathlib, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
java=r'''import java.util.concurrent.*;import java.util.concurrent.atomic.*;
public class FJProfile {
 static final AtomicInteger made=new AtomicInteger(),started=new AtomicInteger(),ended=new AtomicInteger(),names=new AtomicInteger();
 static class Worker extends ForkJoinWorkerThread {
  Worker(ForkJoinPool p){super(p);setName("fixture-"+made.getAndIncrement());}
  protected void onStart(){if(getName().startsWith("fixture-"))names.incrementAndGet();started.incrementAndGet();super.onStart();}
  protected void onTermination(Throwable t){if(t==null)ended.incrementAndGet();super.onTermination(t);}
 }
 static ForkJoinPool pool(int n){return new ForkJoinPool(n,ForkJoinPool.defaultForkJoinWorkerThreadFactory,null,true);}
 public static void main(String[] args)throws Exception{
  ForkJoinPool p=pool(4);AtomicInteger n=new AtomicInteger();for(int i=0;i<4000;i++)p.execute(n::incrementAndGet);p.shutdown();boolean done=p.awaitTermination(5,TimeUnit.SECONDS);boolean rejected=false;try{p.execute(()->{});}catch(RejectedExecutionException e){rejected=true;}System.out.println("work="+n.get()+","+done+","+rejected);
  ForkJoinPool q=pool(1);ForkJoinTask<Integer> parent=q.submit(()->q.submit(()->41).join()+1);System.out.println("nested="+parent.get(5,TimeUnit.SECONDS));q.shutdown();if(!q.awaitTermination(5,TimeUnit.SECONDS))throw new AssertionError();
  ForkJoinPool r=pool(1);CountDownLatch start=new CountDownLatch(1),gate=new CountDownLatch(1);r.execute(()->{start.countDown();try{gate.await();}catch(InterruptedException e){throw new RuntimeException(e);}});start.await();r.shutdown();System.out.println("timeout="+r.awaitTermination(10,TimeUnit.MILLISECONDS));gate.countDown();System.out.println("drained="+r.awaitTermination(5,TimeUnit.SECONDS));
  ForkJoinPool s=pool(1);Future<?> f=s.submit(()->{throw new IllegalArgumentException();});try{f.get();throw new AssertionError();}catch(ExecutionException e){System.out.println("failure=true");}s.shutdown();s.awaitTermination(5,TimeUnit.SECONDS);
  ForkJoinPool custom=new ForkJoinPool(4,Worker::new,null,true);CountDownLatch ready=new CountDownLatch(4);AtomicBoolean release=new AtomicBoolean();for(int i=0;i<4;i++)custom.execute(()->{ready.countDown();while(!release.get())Thread.onSpinWait();});if(!ready.await(5,TimeUnit.SECONDS))throw new AssertionError();release.set(true);custom.shutdown();if(!custom.awaitTermination(5,TimeUnit.SECONDS))throw new AssertionError();System.out.println("life="+made.get()+","+started.get()+","+ended.get()+","+names.get());
 }
}'''
rust=r'''#[path=PATH] mod scheduler;
use scheduler::{WorkerPool,LifecycleHooks};use std::sync::{Arc,Barrier,atomic::{AtomicUsize,Ordering}};use std::time::Duration;
fn main(){
 let p=WorkerPool::new(4).unwrap();let n=Arc::new(AtomicUsize::new(0));for _ in 0..4000{let n=n.clone();p.execute(move||{n.fetch_add(1,Ordering::SeqCst);}).unwrap();}p.close();let done=p.await_closed_idle(Duration::from_secs(5)).unwrap();let rejected=p.execute(||{}).is_err();println!("work={},{},{}",n.load(Ordering::SeqCst),done,rejected);p.shutdown().unwrap();
 let q=Arc::new(WorkerPool::new(1).unwrap());let z=q.clone();let parent=q.submit(move||z.submit(||41).unwrap().get().unwrap()+1).unwrap();println!("nested={}",parent.get().unwrap());q.wait_idle().unwrap();Arc::try_unwrap(q).ok().unwrap().shutdown().unwrap();
 let r=WorkerPool::new(1).unwrap();let start=Arc::new(Barrier::new(2));let gate=Arc::new(Barrier::new(2));let(a,b)=(start.clone(),gate.clone());r.execute(move||{a.wait();b.wait();}).unwrap();start.wait();r.close();println!("timeout={}",r.await_closed_idle(Duration::from_millis(10)).unwrap());gate.wait();println!("drained={}",r.await_closed_idle(Duration::from_secs(5)).unwrap());r.shutdown().unwrap();
 let s=WorkerPool::new(1).unwrap();let f=s.submit(||panic!("expected test panic")).unwrap();println!("failure={}",f.get().is_err());s.shutdown().unwrap();
 let made=Arc::new(AtomicUsize::new(0));let started=Arc::new(AtomicUsize::new(0));let ended=Arc::new(AtomicUsize::new(0));let names=Arc::new(AtomicUsize::new(0));let(a,b,c,d)=(made.clone(),started.clone(),ended.clone(),names.clone());
 let hooks=LifecycleHooks{factory:Arc::new(move|i|{a.fetch_add(1,Ordering::SeqCst);Ok(format!("fixture-{i}"))}),on_start:Arc::new(move|_|{if std::thread::current().name().unwrap_or("").starts_with("fixture-"){d.fetch_add(1,Ordering::SeqCst);}b.fetch_add(1,Ordering::SeqCst);}),on_exit:Arc::new(move|_|{c.fetch_add(1,Ordering::SeqCst);})};
 let custom=WorkerPool::new_with_hooks(4,hooks).unwrap();let end=custom.termination_handle().unwrap();let gate=Arc::new(Barrier::new(5));for _ in 0..4{let g=gate.clone();custom.execute(move||{g.wait();}).unwrap();}gate.wait();custom.shutdown().unwrap();assert_eq!(end.wait(Duration::from_secs(5)).unwrap(),Some(0));println!("life={},{},{},{}",made.load(Ordering::SeqCst),started.load(Ordering::SeqCst),ended.load(Ordering::SeqCst),names.load(Ordering::SeqCst));
}'''.replace('PATH',repr(str(root/'src/rayon_scheduler.rs')).replace("'",'"'))
with tempfile.TemporaryDirectory(prefix='mc-rayon-profile-') as temp:
 d=pathlib.Path(temp);(d/'FJProfile.java').write_text(java);(d/'main.rs').write_text(rust)
 (d/'Cargo.toml').write_text('[package]\nname="mc-aot"\nversion="0.1.0"\nedition="2021"\n[[bin]]\nname="profile"\npath="main.rs"\n[dependencies]\nrayon="=1.11.0"\n')
 (d/'Cargo.lock').write_text((root/'Cargo.lock').read_text())
 subprocess.run([str(jdk/'javac'),str(d/'FJProfile.java')],check=True)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'FJProfile'],capture_output=True,text=True,check=True,timeout=20)
 env=os.environ.copy();env['CARGO_TARGET_DIR']=str(pathlib.Path(tempfile.gettempdir())/'mc-aot-rayon-profile-target')
 r=subprocess.run(['cargo','run','--quiet','--release','--locked','--manifest-path',str(d/'Cargo.toml')],capture_output=True,text=True,env=env,check=True,timeout=90)
 if r.stdout!=j.stdout:raise AssertionError((j.stdout,r.stdout,r.stderr))
 print('OK: 4.000 trabajos, rechazo, espera acotada, join anidado, fallo y conteos de ciclo de vida de 4 hilos contrastados con ForkJoinPool Java 25; el adaptador no es ForkJoinPool completo')
