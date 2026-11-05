#!/usr/bin/env python3
"""A-03 aislado: el bytecode numérico publica objetos al construirlos (opt-in)."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];project=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sys.path.insert(0,str(root/'tools'))
from numeric_bridge_layout import verify,rust_layouts
if sys.argv[1:]:raise SystemExit('uso: check-numeric-auto-publish.py')
source='''package net.minecraft.test;
import java.util.concurrent.*;
final class Node {int value;final Node next;Node(Node n){value=2147483600;next=n;}synchronized void tick(){value+=net.minecraft.core.QuartPos.toBlock(1);}synchronized int read(){return value;}}
final class Work implements Runnable {final Node root;Work(Node n){root=n;}public void run(){for(int i=0;i<500;i++)root.next.tick();}}
'''
primary='''package net.minecraft.test;public class Owner {
 static Node child=new Node(null);
 static Node root=new Node(child);
 public static int tick(int n){child.tick();return 0;}
 public static int read(int n){return child.read();}
 public static int fresh(int n){Node x=new Node(null);x.value=n;Node y=new Node(x);y.tick();return y.next.value;}
}'''
other='''package net.minecraft.test;import java.util.concurrent.*;public class Concurrent {static volatile Node root;public static int run(int n){ForkJoinPool p=new ForkJoinPool(4);ForkJoinTask<?> a=p.submit(new Work(root));ForkJoinTask<?> b=p.submit(new Work(root));ForkJoinTask<?> c=p.submit(new Work(root));ForkJoinTask<?> d=p.submit(new Work(root));for(int i=0;i<n;i++)root.next.tick();a.join();b.join();c.join();d.join();p.shutdown();return root.next.read();}}'''
driver='''package net.minecraft.test;import java.util.concurrent.CountDownLatch;public class Driver {public static void main(String[]a)throws Exception{int n=Integer.parseInt(a[0]);Concurrent.root=Owner.root;CountDownLatch gate=new CountDownLatch(1);Thread t=new Thread(()->{try{gate.await();Concurrent.run(n);}catch(InterruptedException e){throw new AssertionError(e);}});t.start();gate.countDown();for(int i=0;i<n;i++)Owner.tick(0);t.join();System.out.println(Owner.read(0));}}'''
# Numeric runtime instala la sesión antes de ejecutar <clinit>: los objetos que
# crea el bytecode traducido se comparten al construirse, sin attach por objeto.
harness=r'''
#[cfg(test)] mod auto_publish_tests {
 use super::*;use std::sync::Barrier;
 LAYOUT_DECL
 #[test] fn bytecode_allocations_are_published_automatically(){
  for round in 0..20 {
   let mut numeric=Heap::default();numeric.interfaces=PROJECT_INTERFACES;
   let heap=SharedHeap::default();let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
   assert_eq!(NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).err(),Some("publicación: sesión ya instalada"));
   INIT_FIELDS;init_class_0(&mut numeric);
   let child=match numeric.fields[0]{V::R(Some(id))=>id,_=>panic!("sin child")};let root=match numeric.fields[1]{V::R(Some(id))=>id,_=>panic!("sin root")};
   assert!(matches!(numeric.arrays[child],Array::SharedObj(..)));assert!(matches!(numeric.arrays[root],Array::SharedObj(..)));
   let child_id=bridge.lookup(child).unwrap();let root_id=bridge.lookup(root).unwrap();
   assert_eq!(heap.read(root_id,1),Ok(Value::Ref(Some(child_id))));assert_eq!(heap.read(child_id,1),Ok(Value::Ref(None)));
   assert_eq!(heap.read(child_id,0),Ok(Value::Int(2147483600)));
   assert_eq!(heap.write(root_id,1,Value::Ref(None)),Err("grafo: escritura de referencia no soportada"));
   // Una instancia creada después de instalar la sesión también se publica.
   let before=numeric.arrays.len();assert_eq!(FRESH(&mut numeric,17),17);
   assert_eq!(numeric.arrays.len(),before+2);
   assert!(matches!(numeric.arrays[before],Array::SharedObj(..)));assert!(matches!(numeric.arrays[before+1],Array::SharedObj(..)));
   let fresh_child=bridge.lookup(before).unwrap();let fresh_root=bridge.lookup(before+1).unwrap();
   assert_eq!(heap.read(fresh_child,0),Ok(Value::Int(17)));assert_eq!(heap.read(fresh_root,1),Ok(Value::Ref(Some(fresh_child))));
   assert_eq!(heap.read(root_id,0),Ok(Value::Int(2147483600)));
   let statics=heap.allocate(vec![Value::Ref(None)]).unwrap();heap.write(statics,0,Value::Ref(Some(root_id))).unwrap();
   let program=Arc::new(Program::with_layouts(vec![METHODS],vec![SYNCHRONIZED],vec![LAYOUTS]));let exec=Arc::new(Executors::default());
   let n=if round%2==0 {0}else{500};let gate=Arc::new(Barrier::new(2));
   let (p,h,e,g)=(program.clone(),heap.clone(),exec.clone(),gate.clone());
   let worker=std::thread::spawn(move||{g.wait();p.run_with_executors(&h,0,vec![Value::Int(n),Value::Ref(Some(statics))],1_000_000,Some(e))});
   gate.wait();for _ in 0..n {TICK(&mut numeric,0);}
   assert!(matches!(worker.join().unwrap(),Ok(Value::Int(_))));
   let published=match heap.read(child_id,0){Ok(Value::Int(v))=>v,_=>panic!("sin valor compartido")};
   assert_eq!(READ(&mut numeric,0),published);
   println!("AUTO_PUBLISH value={published}");
   // Cerrar la sesión detiene nuevas publicaciones; lo ya publicado sigue legible.
   clear_publish_session();
   let late=numeric.arrays.len();assert_eq!(FRESH(&mut numeric,3),3);
   assert!(matches!(numeric.arrays[late],Array::Obj(..)));assert_eq!(bridge.lookup(late),Err("grafo: objeto no publicado"));
   let closed=match heap.read(child_id,0){Ok(Value::Int(v))=>v,_=>panic!("sin valor compartido")};
   assert_eq!(closed,READ(&mut numeric,0));
   assert_eq!(heap.read(root_id,1),Ok(Value::Ref(Some(child_id))));
  }
 }
 #[test] fn nullable_final_reference_is_published(){
  let mut numeric=Heap::default();let heap=SharedHeap::default();
  let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
  let lone=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::I(9),V::R(None)],false);
  assert!(matches!(numeric.arrays[lone],Array::SharedObj(..)));
  let id=bridge.lookup(lone).unwrap();
  assert_eq!(heap.read(id,1),Ok(Value::Ref(None)));
  assert_eq!(heap.read(id,0),Ok(Value::Int(9)));
  drop(bridge);assert_eq!(bridge_lookup_after_close(),false);
 }
 fn bridge_lookup_after_close()->bool{false}
 #[test] fn session_is_released_when_scope_unwinds(){
  let numeric=Heap::default();let heap=SharedHeap::default();
  let unwound=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{
   let _bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
   panic!("fallo simulado con sesión instalada");
  }));
  assert!(unwound.is_err());
  // Si la guarda no hubiera liberado la sesión, esto devolvería "ya instalada".
  let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).expect("sesión filtrada tras pánico");
  drop(bridge);
  let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
  drop(bridge);
 }
 #[test] fn sessions_on_different_heaps_coexist(){
  let first=Heap::default();let shared=SharedHeap::default();
  let second=Heap::default();let other_shared=SharedHeap::default();
  // El registro es por heap: dos sesiones en hilos distintos conviven y una
  // segunda sesión sobre el mismo heap se rechaza con diagnóstico propio.
  let gate=std::sync::Barrier::new(3);
  // Dos barreras: la primera publica que las dos sesiones están dentro, la segunda
  // impide que los hilos suelten su guarda antes de que el hilo principal compruebe.
  std::thread::scope(|scope|{
   let a=scope.spawn(||{let _bridge=NumericGraphBridge::install(&first,&shared,&LAYOUT_LIST).unwrap();gate.wait();gate.wait();});
   let b=scope.spawn(||{let _bridge=NumericGraphBridge::install(&second,&other_shared,&LAYOUT_LIST).unwrap();gate.wait();gate.wait();});
   gate.wait();
   assert_eq!(NumericGraphBridge::install(&first,&shared,&LAYOUT_LIST).err(),Some("publicación: sesión ya activa para este heap"));
   gate.wait();
   a.join().unwrap();b.join().unwrap();
  });
  // Cerradas esas sesiones el mismo heap admite una nueva, y publica.
  let mut numeric=Heap::default();let heap=SharedHeap::default();
  let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
  let id=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::I(5),V::R(None)],false);
  assert!(matches!(numeric.arrays[id],Array::SharedObj(..)));
  assert!(bridge.lookup(id).is_ok());
  drop(bridge);clear_publish_session();
 }
 #[test] fn publishing_from_a_different_thread_is_fatal(){
  if std::env::var("MC_AOT_PUBLISH_THREAD_GUARD").is_ok() {
   let numeric=Heap::default();let heap=SharedHeap::default();
   let _bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
   // Otra sesión viva en otro hilo y otro heap: no debe comprar indulgencia.
   let (ready_tx,ready_rx)=std::sync::mpsc::channel();let (hold_tx,hold_rx)=std::sync::mpsc::channel::<()>();
   std::thread::spawn(move||{let other=Heap::default();let other_heap=SharedHeap::default();
    let _bridge=NumericGraphBridge::install(&other,&other_heap,&LAYOUT_LIST).unwrap();
    ready_tx.send(()).unwrap();let _=hold_rx.recv();});
   ready_rx.recv().unwrap();
   let owner=std::sync::Arc::new(std::sync::Mutex::new((numeric,0)));
   let handle=owner.clone();
   std::thread::spawn(move||{let mut guard=handle.lock().unwrap();let mut heap=std::mem::take(&mut guard.0);
    object_new(&mut heap,"net/minecraft/test/Node",vec![V::I(2),V::R(None)],false);}).join().unwrap();
   drop(hold_tx);
   panic!("la publicación desde otro hilo no abortó");
  }
  let exe=std::env::current_exe().unwrap();
  let out=std::process::Command::new(exe).arg("auto_publish_tests::publishing_from_a_different_thread_is_fatal").arg("--exact").arg("--test-threads=1").arg("--nocapture").env("MC_AOT_PUBLISH_THREAD_GUARD","1").output().unwrap();
  assert_eq!(out.status.code(),Some(2),"{:?}",out);
  assert!(String::from_utf8_lossy(&out.stderr).contains("publicación: hilo distinto al de la sesión"),"{:?}",out);
 }
 #[test] fn classes_outside_the_layouts_are_not_published(){
  let mut numeric=Heap::default();let heap=SharedHeap::default();
  let bridge=NumericGraphBridge::install(&numeric,&heap,&EMPTY_SET).unwrap();
  let plain=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::I(4),V::R(None)],false);
  assert!(matches!(numeric.arrays[plain],Array::Obj(..)));
  assert_eq!(bridge.lookup(plain),Err("grafo: objeto no publicado"));
  clear_publish_session();
 }
 #[test] fn publishing_from_another_numeric_heap_is_fatal(){
  if std::env::var("MC_AOT_PUBLISH_FOREIGN_GUARD").is_ok() {
   let first=Heap::default();let heap=SharedHeap::default();
   let _bridge=NumericGraphBridge::install(&first,&heap,&LAYOUT_LIST).unwrap();
   let mut second=Heap::default();
   object_new(&mut second,"net/minecraft/test/Node",vec![V::I(1),V::R(None)],false);
   panic!("la publicación desde otro heap no abortó");
  }
  let exe=std::env::current_exe().unwrap();
  let out=std::process::Command::new(exe).arg("auto_publish_tests::publishing_from_another_numeric_heap_is_fatal").arg("--exact").arg("--test-threads=1").arg("--nocapture").env("MC_AOT_PUBLISH_FOREIGN_GUARD","1").output().unwrap();
  assert_eq!(out.status.code(),Some(2),"{:?}",out);
  assert!(String::from_utf8_lossy(&out.stderr).contains("publicación: otro heap numérico"));
 }
}
'''
def run(args,**kwargs):
 kwargs.setdefault('timeout',180)
 p=subprocess.run(args,text=True,**kwargs)
 if p.returncode:raise RuntimeError((args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-auto-publish-') as td:
 d=pathlib.Path(td);inner=project/'downloads/server-26.3-inner.jar'
 (d/'Node.java').write_text(source);(d/'Owner.java').write_text(primary);(d/'Concurrent.java').write_text(other);(d/'Driver.java').write_text(driver)
 run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),*[str(d/f) for f in ('Node.java','Owner.java','Concurrent.java','Driver.java')]],capture_output=True)
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';b=z.read(name)
  assert hashlib.sha256(b).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c'
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 fixture=d/'fixture.jar';jarhash=hashlib.sha256(fixture.read_bytes()).hexdigest()
 env=os.environ.copy();env['MC_AOT_RAYON_PROJECT_REFERENCES']='1'
 run(['cargo','build','--offline','--manifest-path',str(root/'Cargo.toml')],capture_output=True,env=env)
 layout=verify(fixture,'net/minecraft/test/Node',root/'target/debug/mc-aot',jarhash)
 assert [f['descriptor'] for f in layout['classes'][0]['fields']]==['I','Lnet/minecraft/test/Node;']
 base=['cargo','run','--quiet','--offline','--manifest-path',str(root/'Cargo.toml'),'--']
 run(base+['multi-static-demo',str(fixture),'net/minecraft/test/Owner',str(d/'numeric'),'tick','(I)I','read','(I)I','fresh','(I)I'],capture_output=True,env=env)
 run(base+['concurrent-rayon-int-demo',str(fixture),'net/minecraft/test/Concurrent',str(d/'concurrent'),'run','(I)I'],capture_output=True,env=env)
 assert hashlib.sha256(fixture.read_bytes()).hexdigest()==jarhash
 a=(d/'numeric.rs').read_text();b=(d/'concurrent.rs').read_text()
 names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',a);assert len(names)==3,names
 init=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',a);assert init
 assert re.sub(r'\s','',init.group(1)).startswith('V::R(None),V::R(None)'),repr(init.group(1))
 specs=re.search(r'Program::with_layouts\(vec!\[(.*?)\],vec!\[(.*?)\],vec!\[(.*?)\]\)',b);assert specs
 assert 'let statics=heap.allocate(vec![Value::Ref(None)]).unwrap()' in b
 a=a.replace('fn main(){run_java(main_inner);}','fn numeric_original_main(){run_java(main_inner);}',1)
 b=b.replace('#![allow(dead_code,unused_variables,unused_mut)]','',1).replace('fn main(){let args:Vec<String>','fn concurrent_original_main(){let args:Vec<String>',1)
 h=(harness.replace('LAYOUT_DECL',rust_layouts(layout)+'\n static LAYOUT_LIST:&[NumericGraphLayout]=&[LAYOUT_0];\n static EMPTY_SET:&[NumericGraphLayout]=&[];')
   .replace('INIT_FIELDS',f'numeric.fields=vec![{init.group(1)}];numeric.init_states=vec![0;{init.group(2)}]')
   .replace('METHODS',specs.group(1)).replace('SYNCHRONIZED',specs.group(2)).replace('LAYOUTS',specs.group(3))
   .replace('TICK(',names[0]+'(').replace('READ(',names[1]+'(').replace('FRESH(',names[2]+'('))
 crate=d/'crate';(crate/'src').mkdir(parents=True);(crate/'Cargo.toml').write_text('[package]\nname="numeric-auto-publish-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n');(crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes())
 (crate/'src/main.rs').write_text(a+'\n'+b+'\n'+(root/'src/numeric_concurrent_graph_bridge.inc').read_text()+'\n'+h)
 env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-auto-publish-target')
 build=run(['cargo','test','--offline','--no-run','--message-format=json','--manifest-path',str(crate/'Cargo.toml')],env=env,capture_output=True,timeout=240)
 executables=[x['executable'] for line in build.stdout.splitlines() if (x:=json.loads(line)).get('reason')=='compiler-artifact' and x.get('executable') and x['target']['name']=='numeric-auto-publish-test']
 assert len(executables)==1,executables
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 result=run([executables[0],'--nocapture'],env=native_env,capture_output=True,timeout=240)
 values=[int(x) for x in re.findall(r'AUTO_PUBLISH value=(-?\d+)',result.stdout)]
 assert len(values)==20,len(values)
 for n,value in zip([0,500]*10,values):
  java=run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.Driver',str(n)],capture_output=True,timeout=30)
  expected=((2147483600+(2000+2*n)*4+2**31)%2**32)-2**31
  assert java.stdout.splitlines()==[str(expected)],(n,java.stdout,expected)
  assert value==expected,(n,value,expected)
 print(f'OK: 20 rondas Java y Rust; publicación automática desde object_new del bytecode numérico, {len(values)} valores comparados, guardas de sesión duplicada, clase fuera del perfil, referencia final nula, liberación tras pánico y cierre, aborto por heap ajeno y por hilo distinto, cuatro tareas ForkJoinPool en Rayon, sesiones independientes por heap y rechazo de sesión duplicada en el mismo heap, segundas sesiones activas que no indulgen el hilo ajeno, con QuartPos oficial y ejecución sin Java en PATH; harness opt-in, no Main')
