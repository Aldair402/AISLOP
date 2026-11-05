#!/usr/bin/env python3
"""Opt-in de prueba del almacenamiento compartido del runtime numérico real.

NO traduce llamadas Java a Rayon ni modela monitores JVM; inyecta llamadas de
prueba al puente en el Rust generado y usa Rayon solo desde el harness Rust.
"""
import os, pathlib, re, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
interface View {int read();}
final class Cell implements View {int value;Cell alias;int mark;public int read(){return value;}}
public class BridgeFixture {
 static Cell cell=new Cell();static View view=cell;
 static {cell.alias=cell;cell.value=7;}
 public static int run(int n){cell.value=cell.value+n;return cell.alias==cell && view instanceof Cell && view.getClass()==Cell.class?view.read():-1;}
 public static int mark(int n){cell.mark=cell.mark+n;return cell.mark;}
 public static synchronized void guardedAdd(){cell.value++;}
}'''
driver='''import net.minecraft.test.BridgeFixture;
public class Driver{public static void main(String[]a){int[] values={Integer.MIN_VALUE,Integer.MAX_VALUE,-1,0,1};for(int i=0;i<64;i++){int n=i<values.length?values[i]:i-30;System.out.println((i%2==0)?BridgeFixture.run(n):BridgeFixture.mark(n));}}}'''
concurrent_oracle='''import net.minecraft.test.BridgeFixture;import java.util.concurrent.*;
public class ConcurrentOracle {public static void main(String[]a)throws Exception{
 ForkJoinPool pool=new ForkJoinPool(4);CountDownLatch start=new CountDownLatch(1),mid=new CountDownLatch(4),resume=new CountDownLatch(1);ForkJoinTask<?>[] jobs=new ForkJoinTask<?>[4];
 for(int j=0;j<4;j++)jobs[j]=pool.submit(()->{try{start.await();for(int i=0;i<500;i++)BridgeFixture.guardedAdd();mid.countDown();resume.await();for(int i=0;i<500;i++)BridgeFixture.guardedAdd();}catch(InterruptedException e){throw new AssertionError(e);}});
 start.countDown();for(int i=0;i<500;i++)BridgeFixture.mark(1);if(!mid.await(20,TimeUnit.SECONDS))throw new AssertionError("timeout");resume.countDown();for(int i=0;i<500;i++)BridgeFixture.mark(1);for(var job:jobs)job.join();pool.shutdown();
 System.out.println(BridgeFixture.run(0));System.out.println(BridgeFixture.mark(0));
}}'''
harness='''
#[cfg(test)] mod bridge_tests {
 use super::*;
 use std::sync::{Arc,Barrier,mpsc};
 use std::time::Duration;
 #[test] fn actual_numeric_heap_shared_with_rayon(){
  for round in 0..20 {
   let mut heap=Heap::default();heap.interfaces=PROJECT_INTERFACES;INIT_FIELDS;
   assert_eq!(RUN(&mut heap,0),7);
   let id=match heap.fields[0]{V::R(Some(v))=>v,_=>panic!("sin objeto")};
   let elements=heap.elements;let handle=share_project_object(&mut heap,id).unwrap();
   assert_eq!(heap.elements,elements); // se mueve el vector; no duplica campos
   assert!(handle.same_object(&share_project_object(&mut heap,id).unwrap()));
   assert_eq!(resolve_shared_object(&heap,&handle),Ok(id));
   assert!(matches!(object_load(&heap,Some(id),"net/minecraft/test/Cell",1),V::R(Some(x)) if x==id));
   assert_eq!(handle.read_int(0),Ok(7));
   assert_eq!(handle.read_int(1),Err("campo no int"));
   assert_eq!(handle.add_int(1,1),Err("campo no int"));
   assert_eq!(handle.read_int(99),Err("campo inexistente"));
   assert!(share_project_object(&mut heap,usize::MAX).is_err());
   let mut foreign=Heap::default();let foreign_id=object_new(&mut foreign,"net/minecraft/test/Cell",vec![V::I(5)],false);
   let foreign_handle=share_project_object(&mut foreign,foreign_id).unwrap();
   assert_eq!(foreign_id,id); // mismo índice no implica mismo objeto
   assert_eq!(resolve_shared_object(&foreign,&handle),Err("objeto de otro heap"));
   assert_eq!(resolve_shared_object(&heap,&foreign_handle),Err("objeto de otro heap"));
   assert!(!handle.same_object(&foreign_handle));
   assert_eq!(foreign_handle.add_int(0,i32::MAX),Ok(5));
   assert_eq!(foreign_handle.read_int(0),Ok(i32::MIN+4));
   let poison=foreign_handle.clone();
   assert!(std::thread::spawn(move||{let _locked=poison.fields.lock().unwrap();panic!("dañar mutex de prueba")}).join().is_err());
   assert_eq!(foreign_handle.read_int(0),Err("objeto compartido dañado"));
   assert_eq!(foreign_handle.add_int(0,1),Err("objeto compartido dañado"));
   let local=object_new(&mut foreign,"net/minecraft/test/Local",vec![],true);
   assert!(share_project_object(&mut foreign,local).is_err());
   let pool=rayon::ThreadPoolBuilder::new().num_threads(4).build().unwrap();
   let gate=Arc::new(Barrier::new(5));let resume=Arc::new(Barrier::new(5));let(tx,rx)=mpsc::channel();
   for _ in 0..4 {let (obj,gate,resume,tx)=(handle.clone(),gate.clone(),resume.clone(),tx.clone());pool.spawn(move||{gate.wait();for _ in 0..500{obj.add_int(0,1).unwrap();}tx.send(()).unwrap();resume.wait();for _ in 0..500{obj.add_int(0,1).unwrap();}tx.send(()).unwrap();});}
   gate.wait();
   // Bytecode Java traducido toca otro campo entre las fases de las tareas.
   for i in 1..=500 {assert_eq!(MARK(&mut heap,1),i);}
   for _ in 0..4 {rx.recv_timeout(Duration::from_secs(20)).unwrap();}
   resume.wait();for i in 501..=1000 {assert_eq!(MARK(&mut heap,1),i);}
   for _ in 0..4 {rx.recv_timeout(Duration::from_secs(20)).unwrap();}
   assert_eq!(handle.read_int(0),Ok(4007));
   assert_eq!(RUN(&mut heap,round),4007+round);
   assert_eq!(handle.read_int(0),Ok(4007+round));
   assert_eq!(MARK(&mut heap,0),1000);
   assert_eq!(resolve_shared_object(&heap,&handle),Ok(id));
   // El handle no ofrece acceso a referencias, incluso si vive más que el heap.
   drop(heap);assert_eq!(handle.read_int(0),Ok(4007+round));
  }
 }
}
'''
def run(args,**kwargs):
 kwargs.setdefault("timeout",180);return subprocess.run(args,check=True,text=True,**kwargs)
with tempfile.TemporaryDirectory(prefix='mc-numeric-share-') as td:
 d=pathlib.Path(td);(d/'BridgeFixture.java').write_text(source);(d/'Driver.java').write_text(driver);(d/'ConcurrentOracle.java').write_text(concurrent_oracle)
 run([str(jdk/'javac'),'-d',str(d),str(d/'BridgeFixture.java'),str(d/'Driver.java'),str(d/'ConcurrentOracle.java')]);run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/BridgeFixture',str(d/'normal'),'run','(I)I','mark','(I)I'],capture_output=True)
 code=(d/'normal.rs').read_text();names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',code)
 assert len(names)==2,names
 output=run([str(jdk/'java'),'-cp',str(d),'Driver'],capture_output=True).stdout
 args=[]
 for i in range(64):args.extend([str(i%2),str([-2147483648,2147483647,-1,0,1][i] if i<5 else i-30)])
 normal=run([str(d/'normal'),*args],capture_output=True).stdout
 assert output==normal,(output,normal)
 oracle=run([str(jdk/'java'),'-cp',str(d),'ConcurrentOracle'],capture_output=True,timeout=30).stdout
 assert oracle=='4007\n1000\n',oracle
 # Activación opt-in solo en esta prueba, tras el <clinit> real del fixture.
 injected=code
 for name in names:
  head=f'fn {name}(heap: &mut Heap, a0: i32) -> i32 {{\n    init_class_0(heap);'
  assert injected.count(head)==1,head
  injected=injected.replace(head,head+'''\n    let id=match heap.fields[0]{V::R(Some(i))=>i,_=>panic!("sin objeto")};share_project_object(heap,id).unwrap();''',1)
 (d/'injected.rs').write_text(injected)
 run(['rustc','--edition=2021','-O','-C','panic=unwind',str(d/'injected.rs'),'-o',str(d/'injected')],capture_output=True)
 shared=run([str(d/'injected'),*args],capture_output=True).stdout
 assert shared==output,(output,shared)
 # Compilamos el runtime y los métodos generados íntegros con un harness Rayon.
 match=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',code)
 assert match and match.group(1).replace(' ','')=='V::R(None),V::R(None)',match
 init=f'heap.fields=vec![{match.group(1)}];heap.init_states=vec![0;{match.group(2)}]' 
 project=d/'testcrate';project.mkdir();(project/'Cargo.toml').write_text('[package]\nname="numeric-bridge-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n')
 (project/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes());(project/'src').mkdir()
 (project/'src/main.rs').write_text(code+harness.replace('INIT_FIELDS',init).replace('RUN(',names[0]+'(').replace('MARK(',names[1]+'('))
 env=os.environ.copy();env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-rayon-target')
 p=run(['cargo','test','--offline','--manifest-path',str(project/'Cargo.toml'),'--','--nocapture'],env=env,capture_output=True,timeout=240)
 print(p.stdout.strip())
 print('OK: 64 resultados Java/nativo con y sin compartir; 20 rondas Rayon × 4000 incrementos y oráculo Java sincronizado sobre objeto del heap numérico; identidad, alias, campo separado, guardas y pertenencia; no ejecuta tareas Java en Rayon')
# Repetir la conversión con un objeto de Minecraft real: el método que lee su
# campo String es bytecode oficial, no un stub ni una implementación Rust nueva.
import hashlib, zipfile
real_source='''package net.minecraft.test;
import net.minecraft.world.flag.FeatureFlagUniverse;
public class RealBridgeFixture {
 static FeatureFlagUniverse universe=new FeatureFlagUniverse("vanilla"),alias=universe;
 public static int run(int n){return universe==alias && universe.getClass()==FeatureFlagUniverse.class && universe.toString().equals("vanilla")?n+1:-1;}
}'''
real_driver='''import net.minecraft.test.RealBridgeFixture;public class RealDriver {public static void main(String[]a){for(int i=-32;i<32;i++)System.out.println(RealBridgeFixture.run(i));}}'''
with tempfile.TemporaryDirectory(prefix='mc-real-object-share-') as td:
 d=pathlib.Path(td);inner=root.parent/'downloads/server-26.3-inner.jar'
 (d/'RealBridgeFixture.java').write_text(real_source);(d/'RealDriver.java').write_text(real_driver)
 run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'RealBridgeFixture.java'),str(d/'RealDriver.java')])
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/world/flag/FeatureFlagUniverse.class';b=z.read(name)
  assert hashlib.sha256(b).hexdigest()=='61e490913ad43b3f0137a8fd3f310856ef8b06c32051cbc80bc3bfb7c211e2c0'
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RealBridgeFixture',str(d/'native'),'run','(I)I'],capture_output=True)
 code=(d/'native.rs').read_text();names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',code);assert len(names)==1
 head=f'fn {names[0]}(heap: &mut Heap, a0: i32) -> i32 {{\n    init_class_0(heap);';assert code.count(head)==1
 code=code.replace(head,head+'''\n    let id=match heap.fields[0]{V::R(Some(i))=>i,_=>panic!("sin objeto")};share_project_object(heap,id).unwrap();''',1)
 (d/'injected.rs').write_text(code);run(['rustc','--edition=2021','-O','-C','panic=unwind',str(d/'injected.rs'),'-o',str(d/'injected')],capture_output=True)
 java=run([str(jdk/'java'),'-cp',str(d),'RealDriver'],capture_output=True).stdout
 args=[v for n in range(-32,32) for v in ('0',str(n))]
 normal=run([str(d/'native'),*args],capture_output=True).stdout;shared=run([str(d/'injected'),*args],capture_output=True).stdout
 assert len(java.splitlines())==64 and java==normal==shared,(java,normal,shared)
 print('OK: 64 resultados Java/nativo con y sin compartir un FeatureFlagUniverse oficial, hash verificado; campo String accedido por toString oficial, no por el handle')
