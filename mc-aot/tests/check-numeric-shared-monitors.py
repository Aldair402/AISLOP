#!/usr/bin/env python3
"""Intercambia un monitor entre bytecode numérico y tareas Rust/Rayon, opt-in."""
import os,pathlib,re,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
class MonitorBox {int count; synchronized int add(int n){synchronized(this){if(!Thread.holdsLock(this))return -1000;count+=n;return count;}}}
public class MonitorBridge {
 static MonitorBox box=new MonitorBox();
 public static int increment(int n){return box.add(n);}
 public static int outside(int n){return Thread.holdsLock(box)?-10:n;}
 public static int waitUnsupported(int n){try{synchronized(box){box.wait(1);}}catch(InterruptedException e){}return n;}
 public static int fail(int n){try{synchronized(box){if(n!=0)throw new IllegalArgumentException();return Thread.holdsLock(box)?1:-1;}}catch(IllegalArgumentException e){return Thread.holdsLock(box)?-2:2;}}
}'''
driver='''import net.minecraft.test.MonitorBridge;public class Driver{public static void main(String[]a){for(int i=0;i<96;i++){int n=i-48;System.out.println(i%3==0?MonitorBridge.increment(n):i%3==1?MonitorBridge.outside(n):MonitorBridge.fail(i%2));}}}'''
oracle='''import net.minecraft.test.MonitorBridge;import java.util.concurrent.*;
public class Oracle{public static void main(String[]a)throws Exception{ForkJoinPool pool=new ForkJoinPool(4);CountDownLatch gate=new CountDownLatch(1);ForkJoinTask<?>[] tasks=new ForkJoinTask<?>[4];for(int j=0;j<4;j++)tasks[j]=pool.submit(()->{try{gate.await();for(int i=0;i<1000;i++)if(MonitorBridge.increment(1)<1)throw new AssertionError();}catch(InterruptedException e){throw new AssertionError(e);}});gate.countDown();for(int i=0;i<1000;i++)if(MonitorBridge.increment(1)<1)throw new AssertionError();for(var t:tasks)t.join();pool.shutdown();System.out.println(MonitorBridge.increment(0));System.out.println(MonitorBridge.outside(123));System.out.println(MonitorBridge.fail(1));}}'''
harness='''
#[cfg(test)] mod shared_monitor_tests {
 use super::*;use std::sync::{Arc,Barrier,mpsc};use std::time::Duration;
 #[test] fn same_monitor_real_numeric_bytecode_and_rayon_workers(){
  for _round in 0..20{
   let mut h=Heap::default();h.interfaces=PROJECT_INTERFACES;INIT_FIELDS;
   assert_eq!(INCREMENT(&mut h,0),0);let id=match h.fields[0]{V::R(Some(i))=>i,_=>panic!("sin box")};
   monitor_enter(&mut h,Some(id));assert!(monitor_holds(&h,Some(id)));
   assert!(matches!(share_project_object(&mut h,id),Err("monitor monohilo adquirido")));
   monitor_enter(&mut h,Some(id));assert!(matches!(share_project_object(&mut h,id),Err("monitor monohilo adquirido")));monitor_exit(&mut h,Some(id));monitor_exit(&mut h,Some(id));
   let obj=share_project_object(&mut h,id).unwrap();assert!(!monitor_holds(&h,Some(id)));
   // Desbordamiento y envenenamiento del monitor son fallos internos, no Java.
   let mut other_heap=Heap::default();let other_id=object_new(&mut other_heap,"net/minecraft/test/Other",vec![V::I(0)],false);let bad=share_project_object(&mut other_heap,other_id).unwrap();
   {let mut state=bad.monitor.state.lock().unwrap();state.owner=Some(std::thread::current().id());state.depth=usize::MAX;}
   assert!(matches!(bad.enter_monitor(),Err("límite de monitor excedido")));
   {let mut state=bad.monitor.state.lock().unwrap();state.owner=None;state.depth=0;}
   let poisoned=bad.clone();assert!(std::thread::spawn(move||{let _s=poisoned.monitor.state.lock().unwrap();panic!("poison monitor")}).join().is_err());
   assert!(matches!(bad.enter_monitor(),Err("monitor dañado")));
   let g1=obj.enter_monitor().unwrap();assert!(monitor_holds(&h,Some(id)));let g2=obj.enter_monitor().unwrap();
   assert!(share_project_object(&mut h,id).unwrap().same_object(&obj));drop(g2);assert!(monitor_holds(&h,Some(id)));drop(g1);assert!(!monitor_holds(&h,Some(id)));
   // Un propietario distinto no puede salir ni observa holdsLock.
   let(ready_tx,ready_rx)=mpsc::channel();let(release_tx,release_rx)=mpsc::channel();let other=obj.clone();
   let worker=std::thread::spawn(move||{let _g=other.enter_monitor().unwrap();ready_tx.send(()).unwrap();release_rx.recv_timeout(Duration::from_secs(20)).unwrap();});
   ready_rx.recv_timeout(Duration::from_secs(20)).unwrap();assert!(!monitor_holds(&h,Some(id)));
   let p=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||monitor_exit(&mut h,Some(id)))).unwrap_err();
   assert!(p.downcast_ref::<JException>().map_or(false,|e|e.kind=="IllegalMonitorStateException"));release_tx.send(()).unwrap();worker.join().unwrap();
   // El desenrollado Rust libera la guarda sin envenenar el mutex interno.
   let other=obj.clone();assert!(std::thread::spawn(move||{let _g=other.enter_monitor().unwrap();panic!("test unwind");}).join().is_err());
   assert!(!monitor_holds(&h,Some(id)));assert_eq!(FAIL(&mut h,1),2);assert!(!monitor_holds(&h,Some(id)));
   let pool=rayon::ThreadPoolBuilder::new().num_threads(4).build().unwrap();let gate=Arc::new(Barrier::new(5));let(tx,rx)=mpsc::channel();
   for _ in 0..4{let(o,g,tx)=(obj.clone(),gate.clone(),tx.clone());pool.spawn(move||{g.wait();for _ in 0..1000{let _outer=o.enter_monitor().unwrap();let _inner=o.enter_monitor().unwrap();let n=o.read_int(0).unwrap();o.write_int(0,n+1).unwrap();}tx.send(()).unwrap();});}
   gate.wait();for _ in 0..1000 {assert!(INCREMENT(&mut h,1)>0);}for _ in 0..4{rx.recv_timeout(Duration::from_secs(20)).unwrap();}
   assert_eq!(INCREMENT(&mut h,0),5000);assert_eq!(OUTSIDE(&mut h,123),123);assert_eq!(FAIL(&mut h,1),2);assert!(!monitor_holds(&h,Some(id)));
  }
 }
}
'''
def run(args,**kwargs):
 kwargs.setdefault('timeout',180)
 p=subprocess.run(args,text=True,**kwargs)
 if p.returncode:raise RuntimeError((args,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-shared-monitor-') as td:
 d=pathlib.Path(td)
 for n,s in [('MonitorBridge.java',source),('Driver.java',driver),('Oracle.java',oracle)]:(d/n).write_text(s)
 run([str(jdk/'javac'),'-d',str(d),*[str(d/n) for n in ('MonitorBridge.java','Driver.java','Oracle.java')]])
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MonitorBridge',str(d/'native'),'increment','(I)I','outside','(I)I','fail','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 unsupported=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MonitorBridge',str(d/'unsupported'),'waitUnsupported','(I)I'],capture_output=True,text=True,timeout=180)
 assert unsupported.returncode!=0 and 'wait' in unsupported.stderr,unsupported.stderr
 code=(d/'native.rs').read_text();names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',code);assert len(names)==3,names
 args=[]
 for i in range(96):args.extend([str(i%3),str(i-48 if i%3!=2 else i%2)])
 java=run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True).stdout;assert run([str(d/'native'),*args],capture_output=True).stdout==java
 assert run([str(jdk/'java'),'-cp',str(d),'Oracle'],capture_output=True,timeout=30).stdout=='5000\n123\n2\n'
 injected=code
 for name in names:
  head=f'fn {name}(heap: &mut Heap, a0: i32) -> i32 {{\n    init_class_0(heap);';assert injected.count(head)==1
  injected=injected.replace(head,head+'''\n    let id=match heap.fields[0]{V::R(Some(i))=>i,_=>panic!("sin box")};share_project_object(heap,id).unwrap();''',1)
 (d/'injected.rs').write_text(injected);run(['rustc','--edition=2021','-O','-C','panic=unwind',str(d/'injected.rs'),'-o',str(d/'injected')],capture_output=True)
 assert run([str(d/'injected'),*args],capture_output=True).stdout==java
 # La guarda de monitor no puede moverse a un hilo distinto.
 (d/'not_send.rs').write_text(code+"\nfn must_not_compile(o:NumericObjectHandle){let g=o.enter_monitor().unwrap();std::thread::spawn(move||drop(g));}\n")
 bad=subprocess.run(['rustc','--edition=2021',str(d/'not_send.rs'),'-o',str(d/'should-not-exist')],capture_output=True,text=True,timeout=120)
 assert bad.returncode!=0 and 'cannot be sent between threads safely' in bad.stderr and 'Rc<()>' in bad.stderr,bad.stderr
 m=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',code);assert m and m.group(1).replace(' ','')=='V::R(None)'
 init=f'heap.fields=vec![{m.group(1)}];heap.init_states=vec![0;{m.group(2)}]'
 for label,name in zip(('INCREMENT','OUTSIDE','FAIL'),names):harness=harness.replace(label+'(',name+'(')
 crate=d/'crate';(crate/'src').mkdir(parents=True);(crate/'Cargo.toml').write_text('[package]\nname="numeric-monitor-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n')
 (crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes());(crate/'src/main.rs').write_text(code+harness.replace('INIT_FIELDS',init.replace('heap.','h.')))
 env=os.environ.copy();env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-rayon-target')
 p=run(['cargo','test','--offline','--manifest-path',str(crate/'Cargo.toml'),'--','--nocapture'],env=env,capture_output=True,timeout=240)
 print(p.stdout.strip());print('OK: monitor del heap numérico, 96 resultados Java, reentrada, owner, excepción y 20 rondas × 5000 incrementos protegidos por monitor')
