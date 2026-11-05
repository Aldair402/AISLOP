#!/usr/bin/env python3
"""Referencias entre objetos del heap numérico; Rayon solo en harness Rust.

La inyección opt-in activa el puente en Rust generado por multi-static-demo.
No se traduce ForkJoinPool ni se implementa concurrencia Java general.
"""
import os,pathlib,re,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
final class Node {int value;Node next;Node alias;int mark;Object other;int[] data;}
public class ReferenceBridge {
 static Node a=new Node(),b=new Node();
 static {a.value=7;b.value=11;a.next=b;a.alias=b;b.next=a;a.other="text";a.data=new int[1];}
 public static int inspect(int n){return a.alias==b && b.next==a && b.alias==null?(a.next==b?100:200)+n:-999;}
 public static int rewire(int n){a.next=n==0?null:b;return a.next==null?0:1;}
 public static int mark(int n){a.mark+=n;return a.mark;}
 public static int child(int n){return b.value+n;}
 public static synchronized void guardedAdd(){a.value++;b.value++;}
 public static int parent(){return a.value;}
}'''
driver='''import net.minecraft.test.ReferenceBridge;
public class Driver{public static void main(String[]a){for(int i=0;i<96;i++){if(i%3==0)System.out.println(ReferenceBridge.rewire(i%2));else if(i%3==1)System.out.println(ReferenceBridge.inspect(i-50));else System.out.println(ReferenceBridge.child(i));}}}'''
oracle='''import net.minecraft.test.ReferenceBridge;import java.util.concurrent.*;
public class Oracle{public static void main(String[]a)throws Exception{
 ForkJoinPool pool=new ForkJoinPool(4);CountDownLatch start=new CountDownLatch(1),mid=new CountDownLatch(4),resume=new CountDownLatch(1);ForkJoinTask<?>[] jobs=new ForkJoinTask<?>[4];
 for(int j=0;j<4;j++)jobs[j]=pool.submit(()->{try{start.await();for(int i=0;i<500;i++)ReferenceBridge.guardedAdd();mid.countDown();resume.await();for(int i=0;i<500;i++)ReferenceBridge.guardedAdd();}catch(InterruptedException e){throw new AssertionError(e);}});
 start.countDown();for(int i=0;i<500;i++)ReferenceBridge.mark(1);if(!mid.await(20,TimeUnit.SECONDS))throw new AssertionError("timeout");resume.countDown();for(int i=0;i<500;i++)ReferenceBridge.mark(1);for(var j:jobs)j.join();pool.shutdown();System.out.println(ReferenceBridge.parent());System.out.println(ReferenceBridge.child(0));System.out.println(ReferenceBridge.mark(0));
}}'''
harness='''
#[cfg(test)] mod ref_bridge_tests {
 use super::*;use std::sync::{Arc,Barrier,mpsc};use std::time::Duration;
 #[test] fn object_identity_cycles_and_guarded_references(){
  for _round in 0..20 {
   let mut heap=Heap::default();heap.interfaces=PROJECT_INTERFACES;INIT_FIELDS;
   assert_eq!(INSPECT(&mut heap,0),100);
   let aid=match heap.fields[0]{V::R(Some(x))=>x,_=>panic!("sin a")};
   let bid=match heap.fields[1]{V::R(Some(x))=>x,_=>panic!("sin b")};
   let count=heap.elements;let a=share_project_object(&mut heap,aid).unwrap();
   let b=shared_object_reference(&mut heap,&a,1).unwrap().unwrap();
   assert_eq!(heap.elements,count);assert_eq!(resolve_shared_object(&heap,&b),Ok(bid));
   assert!(b.same_object(&shared_object_reference(&mut heap,&a,2).unwrap().unwrap()));
   assert!(a.same_object(&shared_object_reference(&mut heap,&b,1).unwrap().unwrap()));
   assert!(shared_object_reference(&mut heap,&b,2).unwrap().is_none());
   assert!(matches!(shared_object_reference(&mut heap,&a,0),Err("campo no referencia")));
   assert!(matches!(shared_object_reference(&mut heap,&a,99),Err("campo inexistente")));
   assert!(matches!(shared_object_reference(&mut heap,&a,4),Err("solo objetos de proyecto ordinarios"))); // String
   assert!(matches!(shared_object_reference(&mut heap,&a,5),Err("solo objetos de proyecto ordinarios"))); // int[]
   let mut foreign=Heap::default();let fid=object_new(&mut foreign,"net/minecraft/test/Node",vec![V::R(None)],false);
   let f=share_project_object(&mut foreign,fid).unwrap();assert_eq!(fid,aid);
   assert!(matches!(shared_object_reference(&mut foreign,&a,1),Err("objeto de otro heap")));
   assert!(matches!(shared_object_reference(&mut heap,&f,0),Err("objeto de otro heap")));
   let invalid=object_new(&mut foreign,"net/minecraft/test/Bad",vec![V::R(Some(99999))],false);
   let invalid=share_project_object(&mut foreign,invalid).unwrap();
   assert!(matches!(shared_object_reference(&mut foreign,&invalid,0),Err("referencia inválida")));
   let local=object_new(&mut foreign,"net/minecraft/test/Local",vec![],true);
   let wrapping=object_new(&mut foreign,"net/minecraft/test/Bad",vec![V::R(Some(local))],false);
   let wrapping=share_project_object(&mut foreign,wrapping).unwrap();
   assert!(matches!(shared_object_reference(&mut foreign,&wrapping,0),Err("solo objetos de proyecto ordinarios")));
   let poison=f.clone();assert!(std::thread::spawn(move||{let _g=poison.fields.lock().unwrap();panic!("poison")}).join().is_err());
   assert!(matches!(shared_object_reference(&mut foreign,&f,0),Err("objeto compartido dañado")));
   assert_eq!(REWIRE(&mut heap,0),0);assert!(shared_object_reference(&mut heap,&a,1).unwrap().is_none());
   assert_eq!(b.read_int(0),Ok(11)); // el handle previo no se invalida al cambiar el campo
   assert_eq!(REWIRE(&mut heap,1),1);assert!(b.same_object(&shared_object_reference(&mut heap,&a,1).unwrap().unwrap()));
   let pool=rayon::ThreadPoolBuilder::new().num_threads(4).build().unwrap();
   let gate=Arc::new(Barrier::new(5));let resume=Arc::new(Barrier::new(5));let(tx,rx)=mpsc::channel();
   for _ in 0..4 {let (a,b,gate,resume,tx)=(a.clone(),b.clone(),gate.clone(),resume.clone(),tx.clone());pool.spawn(move||{gate.wait();for _ in 0..500{a.add_int(0,1).unwrap();b.add_int(0,1).unwrap();}tx.send(()).unwrap();resume.wait();for _ in 0..500{a.add_int(0,1).unwrap();b.add_int(0,1).unwrap();}tx.send(()).unwrap();});}
   gate.wait();
   for i in 1..=500 {assert_eq!(MARK(&mut heap,1),i);assert_eq!(REWIRE(&mut heap,i&1),i&1);let target=shared_object_reference(&mut heap,&a,1).unwrap();assert_eq!(target.is_some(),i&1==1);if let Some(target)=target {assert!(target.same_object(&b));}}
   for _ in 0..4 {rx.recv_timeout(Duration::from_secs(20)).unwrap();}resume.wait();
   for i in 501..=1000 {assert_eq!(MARK(&mut heap,1),i);assert_eq!(REWIRE(&mut heap,i&1),i&1);}
   for _ in 0..4 {rx.recv_timeout(Duration::from_secs(20)).unwrap();}
   assert_eq!(a.read_int(0),Ok(4007));assert_eq!(b.read_int(0),Ok(4011));assert_eq!(CHILD(&mut heap,0),4011);assert_eq!(MARK(&mut heap,0),1000);
   assert_eq!(REWIRE(&mut heap,1),1);assert_eq!(INSPECT(&mut heap,0),100);
   assert!(b.same_object(&shared_object_reference(&mut heap,&a,1).unwrap().unwrap()));
   assert!(a.same_object(&shared_object_reference(&mut heap,&b,1).unwrap().unwrap()));
   drop(heap);assert_eq!(b.read_int(0),Ok(4011));
  }
 }
}
'''
def run(args,**kwargs):
 kwargs.setdefault('timeout',180);return subprocess.run(args,check=True,text=True,**kwargs)
with tempfile.TemporaryDirectory(prefix='mc-ref-share-') as td:
 d=pathlib.Path(td)
 for n,src in [('ReferenceBridge.java',source),('Driver.java',driver),('Oracle.java',oracle)]:(d/n).write_text(src)
 run([str(jdk/'javac'),'-d',str(d),*[str(d/n) for n in ('ReferenceBridge.java','Driver.java','Oracle.java')]])
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ReferenceBridge',str(d/'native'),'inspect','(I)I','rewire','(I)I','mark','(I)I','child','(I)I'],capture_output=True)
 code=(d/'native.rs').read_text();names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',code);assert len(names)==4,names
 args=[]
 for i in range(96):args.extend(('1',str(i%2)) if i%3==0 else ('0',str(i-50)) if i%3==1 else ('3',str(i)))
 java=run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True).stdout
 normal=run([str(d/'native'),*args],capture_output=True).stdout;assert normal==java
 assert run([str(jdk/'java'),'-cp',str(d),'Oracle'],capture_output=True,timeout=30).stdout=='4007\n4011\n1000\n'
 injected=code
 for name in names:
  head=f'fn {name}(heap: &mut Heap, a0: i32) -> i32 {{\n    init_class_0(heap);';assert injected.count(head)==1
  injected=injected.replace(head,head+'''\n    let id=match heap.fields[0]{V::R(Some(i))=>i,_=>panic!("sin a")};let h=share_project_object(heap,id).unwrap();shared_object_reference(heap,&h,2).unwrap();''',1)
 (d/'injected.rs').write_text(injected);run(['rustc','--edition=2021','-O','-C','panic=unwind',str(d/'injected.rs'),'-o',str(d/'injected')],capture_output=True)
 assert run([str(d/'injected'),*args],capture_output=True).stdout==java
 m=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',code);assert m and m.group(1).replace(' ','')=='V::R(None),V::R(None)'
 init=f'heap.fields=vec![{m.group(1)}];heap.init_states=vec![0;{m.group(2)}]'
 for label,name in zip(('INSPECT','REWIRE','MARK','CHILD'),names):harness=harness.replace(label+'(',name+'(')
 crate=d/'crate';(crate/'src').mkdir(parents=True);(crate/'Cargo.toml').write_text('[package]\nname="numeric-ref-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n')
 (crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes());(crate/'src/main.rs').write_text(code+harness.replace('INIT_FIELDS',init))
 env=os.environ.copy();env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-rayon-target')
 p=run(['cargo','test','--offline','--manifest-path',str(crate/'Cargo.toml'),'--','--nocapture'],env=env,capture_output=True,timeout=240)
 print(p.stdout.strip());print('OK: 96 decisiones con Java 25; 20 rondas × 8000 incrementos sobre dos objetos, alias y ciclo; null, cambio de referencia y guardas; no ejecuta tareas Java en Rayon')
# La segunda parte usa tres classfiles oficiales sin modificar. Solo la
# activación del puente se inyecta en el Rust de prueba, no en los .class.
import hashlib,zipfile
real='''package net.minecraft.world.flag;
public class RealReferenceBridge {
 static FeatureFlagUniverse universe=new FeatureFlagUniverse("vanilla");
 static FeatureFlag first=new FeatureFlag(universe,5),second=new FeatureFlag(universe,32);
 static FeatureFlagSet set=FeatureFlagSet.of(first);
 public static int run(int n){return first.universe==universe && second.universe==universe && set.contains(first) && !set.contains(second)?n+1:-1;}
}'''
realdriver='''import net.minecraft.world.flag.RealReferenceBridge;public class RealDriver {public static void main(String[]a){for(int i=-48;i<48;i++)System.out.println(RealReferenceBridge.run(i));}}'''
hashes={'FeatureFlagUniverse':'61e490913ad43b3f0137a8fd3f310856ef8b06c32051cbc80bc3bfb7c211e2c0','FeatureFlag':'0afc4fc8f08b8c239da2e22cf51a1388cc74991d0b0a73845e121b64f1959c97','FeatureFlagSet':'a09d937bb45d4be48255b51172a40c8ed40c5a2c622437e241a7e49177d378c5'}
with tempfile.TemporaryDirectory(prefix='mc-real-ref-share-') as td:
 d=pathlib.Path(td);inner=root.parent/'downloads/server-26.3-inner.jar';(d/'RealReferenceBridge.java').write_text(real);(d/'RealDriver.java').write_text(realdriver)
 run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'RealReferenceBridge.java'),str(d/'RealDriver.java')])
 with zipfile.ZipFile(inner) as z:
  for name,digest in hashes.items():
   path='net/minecraft/world/flag/'+name+'.class';b=z.read(path);assert hashlib.sha256(b).hexdigest()==digest
   p=d/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/world/flag/RealReferenceBridge',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 code=(d/'native.rs').read_text();names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',code);assert len(names)==1
 head=f'fn {names[0]}(heap: &mut Heap, a0: i32) -> i32 {{\n    init_class_0(heap);';assert code.count(head)==1
 injection='''
    let universe=match heap.fields[0]{V::R(Some(i))=>i,_=>panic!("sin universo")};
    let first=match heap.fields[1]{V::R(Some(i))=>i,_=>panic!("sin flag")};
    let set=match heap.fields[3]{V::R(Some(i))=>i,_=>panic!("sin set")};
    let flag=share_project_object(heap,first).unwrap();let set=share_project_object(heap,set).unwrap();
    let u1=shared_object_reference(heap,&flag,0).unwrap().unwrap();let u2=shared_object_reference(heap,&set,0).unwrap().unwrap();
    assert!(u1.same_object(&u2));assert_eq!(resolve_shared_object(heap,&u1),Ok(universe));
'''
 (d/'injected.rs').write_text(code.replace(head,head+injection,1));run(['rustc','--edition=2021','-O','-C','panic=unwind',str(d/'injected.rs'),'-o',str(d/'injected')],capture_output=True)
 java=run([str(jdk/'java'),'-cp',str(d),'RealDriver'],capture_output=True).stdout;args=[v for i in range(-48,48) for v in ('0',str(i))]
 normal=run([str(d/'native'),*args],capture_output=True).stdout;shared=run([str(d/'injected'),*args],capture_output=True).stdout
 assert len(java.splitlines())==96 and java==normal==shared,(java,normal,shared)
 print('OK: 96 resultados Java/nativo con dos referencias a un universo compartido en FeatureFlag/FeatureFlagSet oficiales; tres hashes verificados; activación experimental solo en la prueba')
