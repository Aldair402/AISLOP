#!/usr/bin/env python3
"""A-06 aislado: arrays de referencias de proyecto compartidos con el puente."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];project=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sys.path.insert(0,str(root/'tools'))
from numeric_bridge_layout import verify,rust_layouts
if sys.argv[1:]:raise SystemExit('uso: check-numeric-shared-arrays.py')
# Un array de proyecto creado en <clinit>, leído y escrito desde el puente.
source='''package net.minecraft.test;
final class Node {int value;Node(int v){value=v;}
 synchronized void bump(){value+=1;}
 synchronized int read(){return value;}}
'''
primary='''package net.minecraft.test;public class Owner {
 static Node[] items;
 static {items=new Node[4];for(int i=0;i<4;i++){items[i]=new Node(i*10);}}
 public static int bump(int n){for(int i=0;i<items.length;i++){items[i].bump();}return items.length;}
 public static int sum(int n){int s=0;for(int i=0;i<items.length;i++){s+=items[i].read();}return s;}
 public static int len(int n){return items.length;}
}'''
driver='''package net.minecraft.test;public class Driver {public static void main(String[] a){
 Owner.bump(0);
 Owner.items[2]=new Node(1000);
 System.out.println(Owner.sum(0));
 System.out.println(Owner.items.length);
 System.out.println(Owner.items[2].read());
}}'''
harness=r"""
#[cfg(test)] mod shared_array_tests {
 use super::*;
 LAYOUT_DECL
 static ARRAY_LAYOUT:NumericGraphArrayLayout=NumericGraphArrayLayout{array_class:"net/minecraft/test/Node[]",element:"net/minecraft/test/Node",length:4};
 #[test] fn project_arrays_are_shared_explicitly(){
  let mut numeric=Heap::default();numeric.interfaces=PROJECT_INTERFACES;
  let heap=SharedHeap::default();let bridge=NumericGraphBridge::install(&numeric,&heap,&LAYOUT_LIST).unwrap();
  INIT_FIELDS;init_class_0(&mut numeric);
  let array=match numeric.fields[0]{V::R(Some(id))=>id,_=>panic!("sin array")};
  // El array NO se publica solo: el subperfil exige adjuntarlo con su layout.
  assert_eq!(bridge.lookup(array),Err("grafo: objeto no publicado"));
  // Guardas del layout antes de adjuntar.
  static WRONG_CLASS:NumericGraphArrayLayout=NumericGraphArrayLayout{array_class:"net/minecraft/test/Node[]",element:"net/minecraft/test/Node2",length:4};
  assert_eq!(bridge.attach_array(&mut numeric,array,&WRONG_CLASS),Err("grafo: clase de array incompatible"));
  static WRONG_LEN:NumericGraphArrayLayout=NumericGraphArrayLayout{array_class:"net/minecraft/test/Node[]",element:"net/minecraft/test/Node",length:5};
  assert_eq!(bridge.attach_array(&mut numeric,array,&WRONG_LEN),Err("grafo: longitud incompatible"));
  let object_id=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::I(1)],false);
  assert_eq!(bridge.attach_array(&mut numeric,object_id,&ARRAY_LAYOUT),Err("grafo: solo arrays de referencias de proyecto"));
  // Adjuntar es idempotente y estable.
  let array_id=bridge.attach_array(&mut numeric,array,&ARRAY_LAYOUT).unwrap();
  assert_eq!(bridge.attach_array(&mut numeric,array,&ARRAY_LAYOUT),Ok(array_id));
  assert_eq!(bridge.lookup(array),Ok(array_id));
  // Los cuatro elementos ya estaban publicados por object_new: se leen tal cual.
  for i in 0..4 {
   let node=match heap.read(array_id,i){Ok(Value::Ref(Some(id)))=>id,_=>panic!("elemento {i} no compartido")};
   assert_eq!(heap.read(node,0),Ok(Value::Int((i as i32)*10)));
  }
  // Guardas de índice y de tipo al escribir desde el heap compartido.
  assert_eq!(heap.read(array_id,4),Err("grafo: índice fuera de rango"));
  assert_eq!(heap.write(array_id,4,Value::Ref(None)),Err("grafo: índice fuera de rango"));
  assert_eq!(heap.write(array_id,0,Value::Int(1)),Err("grafo: tipo de elemento incompatible"));
  let stray=heap.allocate(vec![Value::Int(5)]).unwrap();
  assert_eq!(heap.write(array_id,0,Value::Ref(Some(stray))),Err("grafo: elemento no registrado o incompatible"));
  // Secuencia espejo del Driver Java: bump de los cuatro, sustituir el 2, sumar.
  assert_eq!(BUMP(&mut numeric,0),4);
  let replacement=object_new(&mut numeric,"net/minecraft/test/Node",vec![V::I(1000)],false);
  let replacement_id=bridge.lookup(replacement).unwrap();
  assert_eq!(heap.write(array_id,2,Value::Ref(Some(replacement_id))),Ok(()));
  assert_eq!(heap.read(array_id,2),Ok(Value::Ref(Some(replacement_id))));
  let sum=SUM(&mut numeric,0);
  assert_eq!(sum,1043);
  assert_eq!(LEN(&mut numeric,0),4);
  // Un elemento nulo se comparte como null y el bytecode numérico lo ve.
  assert_eq!(heap.write(array_id,3,Value::Ref(None)),Ok(()));
  assert_eq!(heap.read(array_id,3),Ok(Value::Ref(None)));
  println!("SHARED_ARRAY sum={sum}");
 }
}
"""
def run(args,**kwargs):
 kwargs.setdefault('timeout',180)
 p=subprocess.run(args,text=True,**kwargs)
 if p.returncode:raise RuntimeError((args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-shared-arrays-') as td:
 d=pathlib.Path(td);inner=project/'downloads/server-26.3-inner.jar'
 (d/'Node.java').write_text(source);(d/'Owner.java').write_text(primary);(d/'Driver.java').write_text(driver)
 run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),*[str(d/f) for f in ('Node.java','Owner.java','Driver.java')]],capture_output=True)
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/core/QuartPos.class';b=z.read(name)
  assert hashlib.sha256(b).hexdigest()=='0821d686ee83185e5af97bbfbf384e768c23be925da4edfece98e9a4bb83b62c'
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'])
 fixture=d/'fixture.jar';jarhash=hashlib.sha256(fixture.read_bytes()).hexdigest()
 env=os.environ.copy()
 run(['cargo','build','--offline','--manifest-path',str(root/'Cargo.toml')],capture_output=True,env=env)
 node_layout=verify(fixture,'net/minecraft/test/Node',root/'target/debug/mc-aot',jarhash)
 assert [(f['name'],f['descriptor'],f['kind']) for f in node_layout['classes'][0]['fields']]==[('value','I','int')],node_layout
 layout={'schema':'numeric-graph-layout-v1','jar_sha256':jarhash,'root':'net/minecraft/test/Node','classes':node_layout['classes'],'limitations':node_layout['limitations']}
 base=['cargo','run','--quiet','--offline','--manifest-path',str(root/'Cargo.toml'),'--']
 run(base+['multi-static-demo',str(fixture),'net/minecraft/test/Owner',str(d/'numeric'),'bump','(I)I','sum','(I)I','len','(I)I'],capture_output=True,env=env)
 assert hashlib.sha256(fixture.read_bytes()).hexdigest()==jarhash
 a=(d/'numeric.rs').read_text()
 names=re.findall(r'println!\("\{\}",(numeric_\d+)\(&mut heap, a0\)\)',a);assert len(names)==3,names
 init=re.search(r'heap.fields=vec!\[(.*?)\];heap.init_states=vec!\[0;(\d+)\];',a);assert init
 a=a.replace('fn main(){run_java(main_inner);}','fn numeric_original_main(){run_java(main_inner);}',1)
 decl=rust_layouts(layout)+'\n static LAYOUT_LIST:&[NumericGraphLayout]=&[LAYOUT_0];'
 h=(harness.replace('LAYOUT_DECL',decl)
   .replace('INIT_FIELDS',f'numeric.fields=vec![{init.group(1)}];numeric.init_states=vec![0;{init.group(2)}]')
   .replace('BUMP(',names[0]+'(').replace('SUM(',names[1]+'(').replace('LEN(',names[2]+'('))
 crate=d/'crate';(crate/'src').mkdir(parents=True)
 (crate/'Cargo.toml').write_text('[package]\nname="numeric-shared-arrays-test"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrayon="=1.11.0"\n');(crate/'Cargo.lock').write_bytes((root/'Cargo.lock').read_bytes())
 prelude=('mod concurrent_heap {'+(root/'src/concurrent_heap.rs').read_text()+'}\n'
          'mod scheduler {'+(root/'src/scheduler.rs').read_text()+'}\n'
          'use concurrent_heap::{SharedHeap,Value,ObjectId};\n')
 (crate/'src/main.rs').write_text(a+'\n'+prelude+(root/'src/numeric_concurrent_graph_bridge.inc').read_text()+'\n'+h)
 env['CARGO_TARGET_DIR']=str(pathlib.Path(os.environ.get('TMPDIR','/var/tmp'))/'mc-aot-shared-arrays-target')
 build=run(['cargo','test','--offline','--no-run','--message-format=json','--manifest-path',str(crate/'Cargo.toml')],env=env,capture_output=True,timeout=300)
 executables=[x['executable'] for line in build.stdout.splitlines() if (x:=json.loads(line)).get('reason')=='compiler-artifact' and x.get('executable') and x['target']['name']=='numeric-shared-arrays-test']
 assert len(executables)==1,executables
 result=run([executables[0],'--nocapture'],env=env,capture_output=True,timeout=300)
 assert 'SHARED_ARRAY sum=1043' in result.stdout,result.stdout
 # Diferencial: el mismo programa en Java 25 tras la misma secuencia.
 java=run([str(jdk/'java'),'-cp',str(d),'net.minecraft.test.Driver'],capture_output=True)
 lines=java.stdout.split()
 assert lines==['1043','4','1000'],lines
 print('OK: array de proyecto compartido con el puente (4 elementos, null, sustituto publicado); Java 25 y nativo coinciden en sum=1043 y longitud 4; guardas de clase, longitud, índice, tipo y elemento no publicado; adjuntar es idempotente y el array no se publica solo; harness opt-in, no Main')
