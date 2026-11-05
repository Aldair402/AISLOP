#!/usr/bin/env python3
"""A-04 aislado: escritura de referencias mutables entre backends (opt-in)."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];project=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sys.path.insert(0,str(root/'tools'))
from numeric_bridge_layout import verify,rust_layouts
if sys.argv[1:]:raise SystemExit('uso: check-numeric-mutable-refs.py')
# Lectura y escritura de un campo de referencia NO final, desde ambos backends.
source='''package net.minecraft.test;
import java.util.concurrent.*;
final class Node {int value;final Node next;Node(Node n){value=2147483600;next=n;}
 synchronized void tick(){value+=net.minecraft.core.QuartPos.toBlock(1);}
 synchronized int read(){return value;}}
final class Holder {int value;Node link;Holder(Node n){value=7;link=n;}
 synchronized void link(Node n){link=n;}
 synchronized boolean holds(Node n){return link==n;}}
final class Work implements Runnable {final Node root;Work(Node r){root=r;}
 public void run(){for(int i=0;i<500;i++){root.next.tick();}}}
'''
primary='''package net.minecraft.test;public class Owner {
 static Node child=new Node(null);
 static Node root=new Node(child);
 static Holder holder=new Holder(child);
 public static int tick(int n){child.tick();return 0;}
 public static int read(int n){return child.read();}
 public static int relink(int n){holder.link=child;return holder.link==null?-1:1;}
}'''
other='''package net.minecraft.test;import java.util.concurrent.*;public class Concurrent {static volatile Node root;static volatile Node target;public static int run(int n){ForkJoinPool p=new ForkJoinPool(4);ForkJoinTask<?> a=p.submit(new Work(root));ForkJoinTask<?> b=p.submit(new Work(root));ForkJoinTask<?> c=p.submit(new Work(root));ForkJoinTask<?> d=p.submit(new Work(root));for(int i=0;i<n;i++){target.tick();}a.join();b.join();c.join();d.join();p.shutdown();return root.next==target?1:0;}}'''
driver='''package net.minecraft.test;import java.util.concurrent.CountDownLatch;public class Driver {public static void main(String[]a)throws Exception{int n=Integer.parseInt(a[0]);Concurrent.root=Owner.root;Concurrent.target=Owner.child;CountDownLatch gate=new CountDownLatch(1);Thread t=new Thread(()->{try{gate.await();Concurrent.run(n);}catch(InterruptedException e){throw new AssertionError(e);}});t.start();gate.countDown();for(int i=0;i<n;i++)Owner.tick(0);t.join();System.out.println(Owner.read(0));System.out.println(Owner.holder.holds(Owner.child)?1:0);}}'''
harness=r"""
#[cfg(test)] mod mutable_ref_tests {
 use super::*;
 LAYOUT_DECL
 #[test] fn mutable_reference_fields_cross_the_bridge(){
  for round in 0..20 {
   let mut numeric=Heap::default();numeric.interfaces=PROJECT_INTERFACES;
   let heap=SharedHeap::default();let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
   INIT_FIELDS;init_class_0(&mut numeric);
   let child=match numeric.fields[0]{V::R(Some(id))=>id,_=>panic!("sin child")};
   let root=match numeric.fields[1]{V::R(Some(id))=>id,_=>panic!("sin root")};
   let holder=match numeric.fields[2]{V::R(Some(id))=>id,_=>panic!("sin holder")};
   let child_id=bridge.lookup(child).unwrap();let root_id=bridge.lookup(root).unwrap();let holder_id=bridge.lookup(holder).unwrap();
   // Node.next es final: lectura compartida y escritura rechazada.
   assert_eq!(heap.read(root_id,1),Ok(Value::Ref(Some(child_id))));
   assert_eq!(heap.write(root_id,1,Value::Ref(Some(child_id))),Err("grafo: escritura de referencia no soportada"));
   // Holder.link es escribible: mismo valor, null y de vuelta al destino.
   assert_eq!(heap.read(holder_id,1),Ok(Value::Ref(Some(child_id))));
   assert_eq!(heap.write(holder_id,1,Value::Ref(Some(child_id))),Ok(()));
   assert_eq!(heap.write(holder_id,1,Value::Ref(None)),Ok(()));
   assert_eq!(heap.read(holder_id,1),Ok(Value::Ref(None)));
   let other_holder=object_new(&mut numeric,"net/minecraft/test/Holder",vec![V::I(7),V::R(None)],false);
   let other_holder_id=bridge.lookup(other_holder).unwrap();
   assert_eq!(heap.write(holder_id,1,Value::Ref(Some(other_holder_id))),Err("grafo: destino no registrado o incompatible"));
   assert_eq!(heap.read(holder_id,1),Ok(Value::Ref(None)));
   assert_eq!(heap.write(holder_id,1,Value::Ref(Some(child_id))),Ok(()));
   // Guardas de tipo: int en slot de referencia y referencia en slot int.
   assert_eq!(heap.write(holder_id,1,Value::Int(3)),Err("grafo: tipo de campo incompatible"));
   assert_eq!(heap.write(holder_id,0,Value::Ref(Some(child_id))),Err("grafo: tipo de campo incompatible"));
   let stray=heap.allocate(vec![Value::Int(1),Value::Ref(None)]).unwrap();
   assert_eq!(heap.write(holder_id,1,Value::Ref(Some(stray))),Err("grafo: destino no registrado o incompatible"));
   // El programa concurrente usa dos estáticos: root y target.
   let statics=heap.allocate(vec![Value::Ref(None),Value::Ref(None)]).unwrap();
   heap.write(statics,0,Value::Ref(Some(root_id))).unwrap();heap.write(statics,1,Value::Ref(Some(child_id))).unwrap();
   let program=Arc::new(Program::with_layouts(vec![METHODS],vec![SYNCHRONIZED],vec![LAYOUTS]));let exec=Arc::new(Executors::default());
   let n=if round%2==0 {0}else{500};let gate=std::sync::Arc::new(std::sync::Barrier::new(2));
   let (p,h,e,g)=(program.clone(),heap.clone(),exec.clone(),gate.clone());
   let worker=std::thread::spawn(move||{g.wait();p.run_with_executors(&h,0,vec![Value::Int(n),Value::Ref(Some(statics))],1_000_000,Some(e))});
   gate.wait();for _ in 0..n {TICK(&mut numeric,0);}
   assert_eq!(worker.join().unwrap(),Ok(Value::Int(1)));
   // El bytecode numérico escribe el campo mutable del objeto compartido.
   assert_eq!(RELINK(&mut numeric,0),1);
   assert_eq!(heap.read(holder_id,1),Ok(Value::Ref(Some(child_id))));
   let expected=2147483600_i32.wrapping_add((2000+2*n)*4);
   assert_eq!(heap.read(child_id,0),Ok(Value::Int(expected)));
   assert_eq!(READ(&mut numeric,0),expected);
   println!("MUTABLE_REF value={expected}");
  }
 }
}
"""
def run(args,**kwargs):
 kwargs.setdefault('timeout',180)
 p=subprocess.run(args,text=True,**kwargs)
 if p.returncode:raise RuntimeError((args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-mutable-refs-') as td:
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
 node_layout=verify(fixture,'net/minecraft/test/Node',root/'target/debug/mc-aot',jarhash)
 assert [(f['name'],f['descriptor'],f['kind']) for f in node_layout['classes'][0]['fields']]==[('value','I','int'),('next','Lnet/minecraft/test/Node;','ref')],node_layout
 # Holder.link no es final: sin opt-in el validador debe rechazarlo.
 try:
  verify(fixture,'net/minecraft/test/Holder',root/'target/debug/mc-aot',jarhash)
 except ValueError as e:
  assert 'referencia no final' in str(e),e
 else:raise AssertionError('el validador aceptó una referencia mutable sin opt-in')
 holder_layout=verify(fixture,'net/minecraft/test/Holder',root/'target/debug/mc-aot',jarhash,True)
 assert [(f['name'],f['descriptor'],f['kind']) for f in holder_layout['classes'][0]['fields']]==[('value','I','int'),('link','Lnet/minecraft/test/Node;','mutref')],holder_layout
 layout={'schema':'numeric-graph-layout-v1','jar_sha256':jarhash,'root':'net/minecraft/test/Node','classes':node_layout['classes']+holder_layout['classes'],'limitations':holder_layout['limitations']}
 base=['cargo','run','--quiet','--offline','--manifest-path',str(root/'Cargo.toml'),'--']
 run(base+['multi-static-demo',str(fixture),'net/minecraft/test/Owner',str(d/'numeric'),'tick','(I)I','read','(I)I','relink','(I)I'],capture_output=True,env=env)
 run(base+['concurrent-rayon-int-demo',str(fixture),'net/minecraft/test/Concurrent',str(d/'concurrent'),'run','(I)I'],capture_output=True,env=env)
 assert hashlib.sha256(fixture.read_bytes()).hexdigest()==jarhash
 a=(d/'numeric.rs').read_text();b=(d/'concurrent.rs').read_text()
 names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',a);assert len(names)==3,names
 init=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',a);assert init
 specs=re.search(r'Program::with_layouts\(vec!\[(.*?)\],vec!\[(.*?)\],vec!\[(.*?)\]\)',b);assert specs
 a=a.replace('fn main(){run_java(main_inner);}','fn numeric_original_main(){run_java(main_inner);}',1)
 b=b.replace('#![allow(dead_code,unused_variables,unused_mut)]','',1).replace('fn main(){let args:Vec<String>','fn concurrent_original_main(){let args:Vec<String>',1)
 decl=rust_layouts(layout)+'\n static LAYOUT_LIST:&[NumericGraphLayout]=&[LAYOUT_0,LAYOUT_1];'
 h=(harness.replace('LAYOUT_DECL',decl)
   .replace('INIT_FIELDS',f'numeric.fields=vec![{init.group(1)}];numeric.init_states=vec![0;{init.group(2)}]')
   .replace('METHODS',specs.group(1)).replace('SYNCHRONIZED',specs.group(2)).replace('LAYOUTS',specs.group(3))
   .replace('TICK(',names[0]+'(').replace('READ(',names[1]+'(').replace('RELINK(',names[2]+'('))
 crate=d/'crate';(crate/'src').mkdir(parents=True)
 (crate/'Cargo.toml').write_text('[package]\nname="numeric-mutable-refs-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n');(crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes())
 (crate/'src/main.rs').write_text(a+'\n'+b+'\n'+(root/'src/numeric_concurrent_graph_bridge.inc').read_text()+'\n'+h)
 env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-mutable-target')
 build=run(['cargo','test','--offline','--no-run','--message-format=json','--manifest-path',str(crate/'Cargo.toml')],env=env,capture_output=True,timeout=240)
 executables=[x['executable'] for line in build.stdout.splitlines() if (x:=json.loads(line)).get('reason')=='compiler-artifact' and x.get('executable') and x['target']['name']=='numeric-mutable-refs-test']
 assert len(executables)==1,executables
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 result=run([executables[0],'--nocapture'],env=native_env,capture_output=True,timeout=240)
 values=[int(x) for x in re.findall(r'MUTABLE_REF value=(-?\d+)',result.stdout)]
 assert len(values)==20,len(values)
 for n,value in zip([0,500]*10,values):
  java=run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.Driver',str(n)],capture_output=True,timeout=30)
  expected=((2147483600+(2000+2*n)*4+2**31)%2**32)-2**31
  assert java.stdout.splitlines()==[str(expected),'1'],(n,java.stdout,expected)
  assert value==expected,(n,value,expected)
 print(f'OK: 20 rondas Java y Rust; campo de referencia no final escrito desde el adaptador y desde el bytecode numérico bajo el mutex de campos, {len(values)} valores comparados, identidad del destino, lectura nula, rechazos de destino no publicado y tipos cruzados, campo final sigue solo-lectura, el backend concurrente solo lo lee (B debe permitir campos mutables), cuatro tareas ForkJoinPool en Rayon con QuartPos oficial y ejecución sin Java en PATH; harness opt-in, no Main')
