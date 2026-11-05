#!/usr/bin/env python3
"""Puente aislado opt-in: dos backends, mismo objeto y monitor, FJP Java traducido."""
import hashlib,json,os,pathlib,re,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];project=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
import java.util.concurrent.*;
final class Cell {int value;Cell(){value=2147483600;}synchronized void tick(){value+=net.minecraft.core.QuartPos.toBlock(1);}synchronized int read(){return value;}}
final class Work implements Runnable {final Cell cell;Work(Cell c){cell=c;}public void run(){for(int i=0;i<500;i++)cell.tick();}}
'''
primary='''package net.minecraft.test;public class Owner {static Cell cell=new Cell();public static int tick(int n){cell.tick();return 0;}public static int read(int n){return cell.read();}}'''
other='''package net.minecraft.test;import java.util.concurrent.*;public class Concurrent {static volatile Cell cell;public static int run(int n){ForkJoinPool p=new ForkJoinPool(4);ForkJoinTask<?> a=p.submit(new Work(cell));ForkJoinTask<?> b=p.submit(new Work(cell));ForkJoinTask<?> c=p.submit(new Work(cell));ForkJoinTask<?> d=p.submit(new Work(cell));for(int i=0;i<n;i++)cell.tick();a.join();b.join();c.join();d.join();p.shutdown();return cell.read();}}'''
driver='''package net.minecraft.test;import java.util.concurrent.CountDownLatch;public class Driver {public static void main(String[]a)throws Exception{int n=Integer.parseInt(a[0]);Concurrent.cell=Owner.cell;CountDownLatch gate=new CountDownLatch(1);Thread t=new Thread(()->{try{gate.await();Concurrent.run(n);}catch(InterruptedException e){throw new AssertionError(e);}});t.start();gate.countDown();for(int i=0;i<n;i++)Owner.tick(0);t.join();System.out.println(Owner.read(0));}}'''
# Los valores son deterministas porque todos los incrementos toman el mismo
# monitor. El scheduling de la llamada concurrente es harness de prueba.
harness=r'''
#[cfg(test)] mod bridge_tests {
 use super::*;use std::sync::{mpsc,Barrier};use std::time::Duration;
 #[test] fn real_numeric_and_translated_java_forkjoin_share_object_and_monitor(){
  for round in 0..20 {
   let mut numeric=Heap::default();numeric.interfaces=PROJECT_INTERFACES;INIT_FIELDS;init_class_0(&mut numeric);
   let id=match numeric.fields[0]{V::R(Some(id))=>id,_=>panic!("sin cell")};
   let h=share_project_object(&mut numeric,id).unwrap();let heap=SharedHeap::default();
   let layout=NumericBridgeLayout{class:"net/minecraft/test/Cell",int_fields:1};
   let external=bridge_numeric_object(&mut numeric,&heap,id,&layout).unwrap();
   assert_eq!(bridge_numeric_object(&mut numeric,&heap,id,&layout),Ok(external));
   assert!(bridge_numeric_object(&mut numeric,&heap,id,&NumericBridgeLayout{class:"net/minecraft/test/Other",int_fields:1}).is_err());
   assert!(bridge_numeric_object(&mut numeric,&heap,id,&NumericBridgeLayout{class:"net/minecraft/test/Cell",int_fields:2}).is_err());
   assert_eq!(heap.class_of(external),Ok(Some("net/minecraft/test/Cell")));
   assert_eq!(heap.read(external,0),Ok(Value::Int(2147483600)));
   assert_eq!(heap.read(external,1),Err("campo inexistente"));
   assert_eq!(heap.write(external,0,Value::Long(1)),Err("puente: tipo no soportado"));
   assert_eq!(heap.get_and_add_int(external,0,1),Err("RMW externo no soportado"));
   assert_eq!(heap.compare_exchange(external,0,Value::Int(1),Value::Int(2)),Err("CAS externo no soportado"));
   let other=SharedHeap::default();assert!(other.read(external,0).is_err());
   let other_id=bridge_numeric_object(&mut numeric,&other,id,&layout).unwrap();assert_ne!(external,other_id);assert_eq!(other.read(other_id,0),heap.read(external,0));
   assert_eq!(heap.write(external,0,Value::Ref(None)),Err("puente: solo campos int"));
   // El monitor es el mismo, reentrante incluso al pasar de un backend a otro.
   {let _one=h.enter_monitor().unwrap();let _two=heap.enter(external).unwrap();assert_eq!(h.monitor.holds(),Ok(true));}
   {let _one=heap.enter(external).unwrap();let _two=h.enter_monitor().unwrap();assert_eq!(h.monitor.holds(),Ok(true));}
   assert_eq!(h.monitor.holds(),Ok(false));
   let (started,ready)=mpsc::channel();let (done,received)=mpsc::channel();let h2=heap.clone();
   let guard=h.enter_monitor().unwrap();let waiter=std::thread::spawn(move||{started.send(()).unwrap();let _g=h2.enter(external).unwrap();done.send(()).unwrap();});
   ready.recv_timeout(Duration::from_secs(5)).unwrap();assert!(received.recv_timeout(Duration::from_millis(20)).is_err());
   // Una espera en el monitor externo no puede retener el mutex del SharedHeap.
   let check=heap.clone();let (ptx,prx)=mpsc::channel();let probe=std::thread::spawn(move||{ptx.send(check.read(external,0)).unwrap();});
   let visible=prx.recv_timeout(Duration::from_secs(2));drop(guard);received.recv_timeout(Duration::from_secs(5)).unwrap();waiter.join().unwrap();probe.join().unwrap();assert_eq!(visible,Ok(Ok(Value::Int(2147483600))));
   if round==0 {let h3=heap.clone();assert!(std::thread::spawn(move||{let _g=h3.enter(external).unwrap();panic!("desenrollado de prueba")}).join().is_err());let _again=h.enter_monitor().unwrap();}
   let bad=object_new(&mut numeric,"net/minecraft/test/Bad",vec![V::R(None)],false);assert!(matches!(bridge_numeric_object(&mut numeric,&heap,bad,&NumericBridgeLayout{class:"net/minecraft/test/Bad",int_fields:1}),Err("puente: layout int incompatible")));
   let local=object_new(&mut numeric,"net/minecraft/test/Local",vec![],true);assert!(bridge_numeric_object(&mut numeric,&heap,local,&NumericBridgeLayout{class:"net/minecraft/test/Local",int_fields:0}).is_err());
   let statics=heap.allocate(vec![Value::Ref(None)]).unwrap();heap.write(statics,0,Value::Ref(Some(external))).unwrap();
   let program=Arc::new(Program::with_layouts(vec![METHODS],vec![SYNCHRONIZED],vec![LAYOUTS]));let exec=Arc::new(Executors::default());
   let n=if round%2==0 {0}else{500};let gate=Arc::new(Barrier::new(2));
   let (p,h2,e,g)=(program.clone(),heap.clone(),exec.clone(),gate.clone());
   let worker=std::thread::spawn(move||{g.wait();p.run_with_executors(&h2,0,vec![Value::Int(n),Value::Ref(Some(statics))],1_000_000,Some(e))});
   gate.wait();for _ in 0..n {TICK(&mut numeric,0);}
   assert!(matches!(worker.join().unwrap(),Ok(Value::Int(_))));
   let expected=2147483600_i32.wrapping_add((2000+2*n)*4);assert_eq!(READ(&mut numeric,0),expected);assert_eq!(heap.read(external,0),Ok(Value::Int(expected)));
   drop(numeric);assert_eq!(heap.read(external,0),Ok(Value::Int(expected)));assert_eq!(other.read(other_id,0),Ok(Value::Int(expected)));
  }
 }
}
'''
def run(args,**kwargs):kwargs.setdefault('timeout',180);return subprocess.run(args,check=True,text=True,**kwargs)
with tempfile.TemporaryDirectory(prefix='mc-two-runtime-bridge-') as td:
 d=pathlib.Path(td);inner=project/'downloads/server-26.3-inner.jar'
 # Java permite una sola clase pública por archivo.
 (d/'Cell.java').write_text(source);(d/'Owner.java').write_text(primary);(d/'Concurrent.java').write_text(other);(d/'Driver.java').write_text(driver)
 run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),*[str(d/f) for f in ('Cell.java','Owner.java','Concurrent.java','Driver.java')]],capture_output=True)
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';b=z.read(name);assert hashlib.sha256(b).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c';p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 # Verifica layout real antes de crear el puente: V::I también representa
 # byte/char/short/boolean y no basta para reconocer un campo int.
 cellbytes=(d/'net/minecraft/test/Cell.class').read_bytes();cellhash=hashlib.sha256(cellbytes).hexdigest()
 base=['cargo','run','--quiet','--offline','--manifest-path',str(root/'Cargo.toml'),'--']
 env=os.environ.copy();env['MC_AOT_RAYON_PROJECT_REFERENCES']='1'
 inspect=run(base+['inspect',str(d/'fixture.jar'),'net/minecraft/test/Cell'],capture_output=True,env=env).stdout
 assert 'Clase: net/minecraft/test/Cell\nSuperclase: java/lang/Object' in inspect and re.search(r'^Interfaces: *$',inspect,re.M) and '<clinit>()V' not in inspect and re.search(r'^Flags: 0x[0-9a-f]+$',inspect,re.M)
 flags=int(re.search(r'^Flags: 0x([0-9a-f]+)$',inspect,re.M).group(1),16);assert flags&0x10 and not flags&0x600
 fields=inspect.split('Campos (',1)[1].split('\n\n',1)[0];assert re.findall(r'^  0x([0-9a-f]{4}) (\S+) (\S+)$',fields,re.M)==[('0000','value','I')],fields
 run(base+['multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Owner',str(d/'numeric'),'tick','(I)I','read','(I)I'],capture_output=True,env=env)
 run(base+['concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/Concurrent',str(d/'concurrent'),'run','(I)I'],capture_output=True,env=env)
 assert hashlib.sha256((d/'net/minecraft/test/Cell.class').read_bytes()).hexdigest()==cellhash
 a=(d/'numeric.rs').read_text();b=(d/'concurrent.rs').read_text()
 names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',a);assert len(names)==2,names
 init=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',a);assert init
 assert re.sub(r'\s','',init.group(1)).startswith('V::R(None)'),repr(init.group(1))
 specs=re.search(r'Program::with_layouts\(vec!\[(.*?)\],vec!\[(.*?)\],vec!\[(.*?)\]\)',b);assert specs
 assert 'let statics=heap.allocate(vec![Value::Ref(None)]).unwrap()' in b
 a=a.replace('fn main(){run_java(main_inner);}','fn numeric_original_main(){run_java(main_inner);}',1)
 b=b.replace('#![allow(dead_code,unused_variables,unused_mut)]','',1).replace('fn main(){let args:Vec<String>','fn concurrent_original_main(){let args:Vec<String>',1)
 h=harness.replace('INIT_FIELDS',f'numeric.fields=vec![{init.group(1)}];numeric.init_states=vec![0;{init.group(2)}]').replace('METHODS',specs.group(1)).replace('SYNCHRONIZED',specs.group(2)).replace('LAYOUTS',specs.group(3)).replace('TICK(',names[0]+'(').replace('READ(',names[1]+'(')
 crate=d/'crate';(crate/'src').mkdir(parents=True);(crate/'Cargo.toml').write_text('[package]\nname="numeric-concurrent-bridge-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n');(crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes());(crate/'src/main.rs').write_text(a+'\n'+b+'\n'+(root/'src/numeric_concurrent_bridge.inc').read_text()+'\n'+h)
 env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-bridge-target')
 build=run(['cargo','test','--offline','--no-run','--message-format=json','--manifest-path',str(crate/'Cargo.toml')],env=env,capture_output=True,timeout=240)
 executables=[x['executable'] for line in build.stdout.splitlines() if (x:=json.loads(line)).get('reason')=='compiler-artifact' and x.get('executable') and x['target']['name']=='numeric-concurrent-bridge-test']
 assert len(executables)==1,executables
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 result=run([executables[0],'--nocapture'],env=native_env,capture_output=True,timeout=240);print(result.stdout.strip())
 for n in [0,500]*10:
  java=run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.Driver',str(n)],capture_output=True,timeout=30)
  expected=((2147483600+(2000+2*n)*4+2**31)%2**32)-2**31
  assert java.stdout==f'{expected}\n',(java.stdout,expected)
 print('OK: 20 rondas Java y Rust; dos backends traducidos, mismo objeto y monitor; cuatro tareas ForkJoinPool Java en Rayon, QuartPos oficial, alias, reentrada y guardas, ejecución sin Java en PATH; harness externo opt-in, no Main')
