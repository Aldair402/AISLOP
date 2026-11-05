#!/usr/bin/env python3
"""Inventario de invocaciones directas. No prueba ejecución, cobertura ni lambdas."""
import argparse,collections,csv,pathlib,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from scan_bytecode import parse,instructions,resolve
ap=argparse.ArgumentParser();ap.add_argument('jar',type=pathlib.Path);ap.add_argument('output',type=pathlib.Path);args=ap.parse_args()
owners={'java/util/concurrent/Executor','java/util/concurrent/ExecutorService','java/util/concurrent/ForkJoinPool','java/util/concurrent/ForkJoinTask','java/util/concurrent/CompletableFuture','net/minecraft/TracingExecutor'}
rows=[];errors=[]
with zipfile.ZipFile(args.jar) as z:
 for entry in z.infolist():
  if not entry.filename.endswith('.class'):continue
  try:
   cp,methods=parse(z.read(entry))
   for _,method,desc,code in methods:
    ops=list(instructions(code));dynamics=sum(op==0xba for _,op,_ in ops)
    for offset,op,data in ops:
     if op not in (0xb6,0xb7,0xb8,0xb9):continue
     ref=resolve(cp,int.from_bytes(data[:2],'big'))
     if ref and ref[0] in owners:rows.append((entry.filename[:-6],method,desc,offset,hex(op),*ref,dynamics))
  except Exception as e:errors.append((entry.filename,str(e)))
if errors:
 print('ERRORES DE INVENTARIO:',errors[:10],file=sys.stderr);sys.exit(1)
rows.sort();args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('w',newline='',encoding='utf-8') as f:
 w=csv.writer(f,delimiter='\t');w.writerow(['clase','metodo','descriptor','offset','opcode','owner','callee','descriptor_destino','invokedynamic_en_metodo']);w.writerows(rows)
print('JAR:',args.jar,'referencias directas:',len(rows),'clases:',len({r[0] for r in rows}),'metodos:',len({r[:3] for r in rows}))
print('Por propietario:')
for owner,n in sorted(collections.Counter(r[5] for r in rows).items()):print(f'  {owner}: {n}')
print('Llamadas en métodos con al menos un invokedynamic:',sum(bool(r[8]) for r in rows))
print('El contador invokedynamic incluye también concat y otros bootstraps; no identifica lambda ni su relación con la llamada.')
print('Solo invocaciones directas en el JAR indicado; no muestra ejecución, despacho por otros tipos, reflexión, bibliotecas ni cobertura real.')
