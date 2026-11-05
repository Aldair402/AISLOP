#!/usr/bin/env python3
"""Puente aislado opt-in: dos backends, mismo objeto y monitor, FJP Java traducido."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];project=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
if sys.argv[1:] not in ([],['--ticktask']):raise SystemExit('uso: check-numeric-concurrent-graph.py [--ticktask]')
ticktask=sys.argv[1:]==['--ticktask']
source='''package net.minecraft.test;
import java.util.concurrent.*;
final class Node {int value;final Node next;Node(Node n){value=2147483600;next=n;}synchronized void tick(){value+=net.minecraft.core.QuartPos.toBlock(1);}synchronized int read(){return value;}}
final class Work implements Runnable {final Node root;Work(Node n){root=n;}public void run(){for(int i=0;i<500;i++)root.next.tick();}}
'''
primary='''package net.minecraft.test;public class Owner {static Node child=new Node(null);static Node root=new Node(child);public static int tick(int n){child.tick();return 0;}public static int read(int n){return child.read();}}'''
other='''package net.minecraft.test;import java.util.concurrent.*;public class Concurrent {static volatile Node root;public static int run(int n){ForkJoinPool p=new ForkJoinPool(4);ForkJoinTask<?> a=p.submit(new Work(root));ForkJoinTask<?> b=p.submit(new Work(root));ForkJoinTask<?> c=p.submit(new Work(root));ForkJoinTask<?> d=p.submit(new Work(root));for(int i=0;i<n;i++)root.next.tick();a.join();b.join();c.join();d.join();p.shutdown();return root.next.read();}}'''
if ticktask:
 old='ForkJoinTask<?> a=p.submit(new Work(root));ForkJoinTask<?> b=p.submit(new Work(root));ForkJoinTask<?> c=p.submit(new Work(root));ForkJoinTask<?> d=p.submit(new Work(root));'
 replacement='net.minecraft.server.TickTask ta=new net.minecraft.server.TickTask(7,new Work(root));if(ta.getTick()!=7)return 777;ForkJoinTask<?> a=p.submit(ta);ForkJoinTask<?> b=p.submit(new net.minecraft.server.TickTask(8,new Work(root)));ForkJoinTask<?> c=p.submit(new net.minecraft.server.TickTask(9,new Work(root)));ForkJoinTask<?> d=p.submit(new net.minecraft.server.TickTask(10,new Work(root)));'
 assert old in other;other=other.replace(old,replacement)
driver='''package net.minecraft.test;import java.util.concurrent.CountDownLatch;public class Driver {public static void main(String[]a)throws Exception{int n=Integer.parseInt(a[0]);Concurrent.root=Owner.root;CountDownLatch gate=new CountDownLatch(1);Thread t=new Thread(()->{try{gate.await();Concurrent.run(n);}catch(InterruptedException e){throw new AssertionError(e);}});t.start();gate.countDown();for(int i=0;i<n;i++)Owner.tick(0);t.join();System.out.println(Owner.read(0));}}'''
# Los valores son deterministas porque todos los incrementos toman el mismo
# monitor. El scheduling de la llamada concurrente es harness de prueba.
harness=r'''
#[cfg(test)] mod graph_tests {
 use super::*;use std::sync::Barrier;
 static LAYOUT:NumericGraphLayout=NumericGraphLayout{class:"net/minecraft/test/Node",fields:&[NumericGraphSlot::Int,NumericGraphSlot::Ref("net/minecraft/test/Node")]};
 static WRONG:NumericGraphLayout=NumericGraphLayout{class:"net/minecraft/test/Node",fields:&[NumericGraphSlot::Int,NumericGraphSlot::Int]};
 #[test] fn graph_traversal_between_backends(){
  for round in 0..20 {
   let mut numeric=Heap::default();numeric.interfaces=PROJECT_INTERFACES;INIT_FIELDS;init_class_0(&mut numeric);
   let child=match numeric.fields[0]{V::R(Some(id))=>id,_=>panic!("sin child")};let root=match numeric.fields[1]{V::R(Some(id))=>id,_=>panic!("sin root")};
   let heap=SharedHeap::default();let bridge=NumericGraphBridge::new(&numeric,&heap);
   let root_id=bridge.attach(&mut numeric,root,&LAYOUT).unwrap();assert_eq!(bridge.attach(&mut numeric,root,&LAYOUT),Ok(root_id));
   assert_eq!(heap.read(root_id,1),Err("grafo: destino no registrado o incompatible"));
   let child_id=bridge.attach(&mut numeric,child,&LAYOUT).unwrap();assert_eq!(heap.read(root_id,1),Ok(Value::Ref(Some(child_id))));
   assert_eq!(heap.read(child_id,1),Ok(Value::Ref(None)));assert_eq!(heap.read(root_id,0),Ok(Value::Int(2147483600)));
   assert_eq!(heap.write(root_id,1,Value::Ref(None)),Err("grafo: escritura de referencia no soportada"));
   assert!(bridge.attach(&mut numeric,root,&WRONG).is_err());
   let mut foreign=Heap::default();let foreign_id=object_new(&mut foreign,"net/minecraft/test/Node",vec![V::I(5),V::R(None)],false);assert_eq!(bridge.attach(&mut foreign,foreign_id,&LAYOUT),Err("grafo: otro heap numérico"));
   let other=SharedHeap::default();assert!(other.read(root_id,0).is_err());
   let broken=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::I(0),V::R(Some(99999))],false);let broken_id=bridge.attach(&mut numeric,broken,&LAYOUT).unwrap();assert_eq!(heap.read(broken_id,1),Err("grafo: destino no registrado o incompatible"));
   let invalid=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::R(None),V::R(None)],false);assert_eq!(bridge.attach(&mut numeric,invalid,&LAYOUT),Err("grafo: layout incompatible"));assert!(matches!(numeric.arrays[invalid],Array::Obj(_,_)));
   let alien=other.allocate(vec![]).unwrap();assert!(heap.write(root_id,1,Value::Ref(Some(alien))).is_err());
   let another=NumericGraphBridge::new(&numeric,&heap);assert_eq!(another.attach(&mut numeric,root,&LAYOUT),Err("identidad externa incompatible"));
   if round==0 { // Incluso un adaptador interno defectuoso no puede devolver IDs ajenos.
    struct Bad(concurrent_heap::ObjectId);impl concurrent_heap::ExternalObject for Bad {
      fn identity_key(&self)->usize{usize::MAX} fn domain_key(&self)->usize{usize::MAX} fn class(&self)->&'static str{"net/minecraft/test/Bad"}
      fn field_count(&self)->Result<usize,&'static str>{Ok(1)} fn read(&self,_:usize)->Result<concurrent_heap::ExternalValue,&'static str>{Ok(concurrent_heap::ExternalValue::Ref(Some(self.0)))}
      fn write(&self,_:usize,_:concurrent_heap::ExternalValue)->Result<(),&'static str>{Err("no")}
      fn enter(&self)->Result<Box<dyn concurrent_heap::ExternalGuard>,&'static str>{Err("no")}
    }
    let bad=heap.attach_external(Arc::new(Bad(alien))).unwrap();assert_eq!(heap.read(bad,0),Err("objeto inválido"));
   }
   let statics=heap.allocate(vec![Value::Ref(None)]).unwrap();heap.write(statics,0,Value::Ref(Some(root_id))).unwrap();
   let program=Arc::new(Program::with_layouts(vec![METHODS],vec![SYNCHRONIZED],vec![LAYOUTS]));let exec=Arc::new(Executors::default());
   let n=if round%2==0 {0}else{500};let gate=Arc::new(Barrier::new(2));
   let (p,h,e,g)=(program.clone(),heap.clone(),exec.clone(),gate.clone());
   let worker=std::thread::spawn(move||{g.wait();p.run_with_executors(&h,0,vec![Value::Int(n),Value::Ref(Some(statics))],1_000_000,Some(e))});
   gate.wait();for _ in 0..n {TICK(&mut numeric,0);}
   assert!(matches!(worker.join().unwrap(),Ok(Value::Int(_))));let expected=2147483600_i32.wrapping_add((2000+2*n)*4);
   assert_eq!(READ(&mut numeric,0),expected);assert_eq!(heap.read(child_id,0),Ok(Value::Int(expected)));assert_eq!(heap.read(root_id,1),Ok(Value::Ref(Some(child_id))));
   drop(bridge);assert_eq!(heap.read(root_id,0),Err("grafo: sesión cerrada"));assert!(heap.enter(root_id).is_err());
  }
 }
}
'''
def run(args,**kwargs):
 kwargs.setdefault('timeout',180)
 p=subprocess.run(args,text=True,**kwargs)
 if p.returncode:raise RuntimeError((args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-two-runtime-bridge-') as td:
 d=pathlib.Path(td);inner=project/'downloads/server-26.3-inner.jar'
 # Java permite una sola clase pública por archivo.
 (d/'Node.java').write_text(source);(d/'Owner.java').write_text(primary);(d/'Concurrent.java').write_text(other);(d/'Driver.java').write_text(driver)
 run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),*[str(d/f) for f in ('Node.java','Owner.java','Concurrent.java','Driver.java')]],capture_output=True)
 with zipfile.ZipFile(inner) as z:
  classes=[('net/minecraft/core/QuartPos.class','0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c')]
  if ticktask:classes.append(('net/minecraft/server/TickTask.class','dae918ab7da617b85384411773b9759ffbc0c0609bfc06c7dc4af85b76fa69b6'))
  for name,digest in classes:
   b=z.read(name);assert hashlib.sha256(b).hexdigest()==digest;p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 # Verifica layout real antes de crear el puente: V::I también representa
 # byte/char/short/boolean y no basta para reconocer un campo int.
 cellbytes=(d/'net/minecraft/test/Node.class').read_bytes();cellhash=hashlib.sha256(cellbytes).hexdigest()
 base=['cargo','run','--quiet','--offline','--manifest-path',str(root/'Cargo.toml'),'--']
 env=os.environ.copy();env['MC_AOT_RAYON_PROJECT_REFERENCES']='1'
 inspect=run(base+['inspect',str(d/'fixture.jar'),'net/minecraft/test/Node'],capture_output=True,env=env).stdout
 assert 'Clase: net/minecraft/test/Node\nSuperclase: java/lang/Object' in inspect and re.search(r'^Interfaces: *$',inspect,re.M) and '<clinit>()V' not in inspect and re.search(r'^Flags: 0x[0-9a-f]+$',inspect,re.M)
 flags=int(re.search(r'^Flags: 0x([0-9a-f]+)$',inspect,re.M).group(1),16);assert flags&0x10 and not flags&0x600
 fields=inspect.split('Campos (',1)[1].split('\n\n',1)[0];assert re.findall(r'^  0x([0-9a-f]{4}) (\S+) (\S+)$',fields,re.M)==[('0000','value','I'),('0010','next','Lnet/minecraft/test/Node;')],fields
 run(base+['multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Owner',str(d/'numeric'),'tick','(I)I','read','(I)I'],capture_output=True,env=env)
 run(base+['concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/test/Concurrent',str(d/'concurrent'),'run','(I)I'],capture_output=True,env=env)
 assert hashlib.sha256((d/'net/minecraft/test/Node.class').read_bytes()).hexdigest()==cellhash
 a=(d/'numeric.rs').read_text();b=(d/'concurrent.rs').read_text()
 names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',a);assert len(names)==2,names
 init=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',a);assert init
 assert re.sub(r'\s','',init.group(1)).startswith('V::R(None),V::R(None)'),repr(init.group(1))
 specs=re.search(r'Program::with_layouts\(vec!\[(.*?)\],vec!\[(.*?)\],vec!\[(.*?)\]\)',b);assert specs
 assert 'let statics=heap.allocate(vec![Value::Ref(None)]).unwrap()' in b
 a=a.replace('fn main(){run_java(main_inner);}','fn numeric_original_main(){run_java(main_inner);}',1)
 b=b.replace('#![allow(dead_code,unused_variables,unused_mut)]','',1).replace('fn main(){let args:Vec<String>','fn concurrent_original_main(){let args:Vec<String>',1)
 h=harness.replace('INIT_FIELDS',f'numeric.fields=vec![{init.group(1)}];numeric.init_states=vec![0;{init.group(2)}]').replace('METHODS',specs.group(1)).replace('SYNCHRONIZED',specs.group(2)).replace('LAYOUTS',specs.group(3)).replace('TICK(',names[0]+'(').replace('READ(',names[1]+'(')
 crate=d/'crate';(crate/'src').mkdir(parents=True);(crate/'Cargo.toml').write_text('[package]\nname="numeric-concurrent-bridge-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n');(crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes());(crate/'src/main.rs').write_text(a+'\n'+b+'\n'+(root/'src/numeric_concurrent_graph_bridge.inc').read_text()+'\n'+h)
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
 print(f'OK: 20 rondas Java y Rust; dos backends traducidos, navegación de referencia final entre dos objetos y monitor compartido; cuatro tareas ForkJoinPool Java en Rayon, {"TickTask y " if ticktask else ""}QuartPos oficial, alias y guardas de identidad, registro y tipo, ejecución sin Java en PATH; harness externo opt-in, no Main')
