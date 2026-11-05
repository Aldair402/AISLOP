#!/usr/bin/env python3
"""Audita únicamente métodos static con manejadores de la jerarquía limitada implementada."""
import collections,concurrent.futures,json,pathlib,re,subprocess,tempfile,zipfile
import scan_bytecode
root=pathlib.Path(__file__).resolve().parent;jar=root.parent/'downloads/server-26.3-inner.jar';report=root.parent/'analysis/audit-exceptions.json'
allowed={'java/lang/Throwable','java/lang/Exception','java/lang/RuntimeException','java/lang/IllegalArgumentException','java/lang/NumberFormatException','java/io/IOException','java/lang/IndexOutOfBoundsException','java/lang/ArithmeticException','java/lang/NullPointerException','java/lang/ArrayIndexOutOfBoundsException','java/lang/StringIndexOutOfBoundsException','java/lang/NegativeArraySizeException','java/lang/ClassCastException','java/lang/ArrayStoreException'}
sig=re.compile(r'^\((?:(?:\[?Ljava/lang/String;)|\[?[IJZBCS])*\)(?:[IJZBCSJV]|Ljava/lang/String;)$')
def parse(data):
 r=scan_bytecode.R(data)
 if r.u4()!=0xcafebabe:raise ValueError('magic')
 r.take(4);size=r.u2();cp=[None]*size;i=1
 while i<size:
  tag=r.u1()
  if tag==1:cp[i]=('utf',r.take(r.u2()).decode('utf8','replace'))
  elif tag in (3,4):r.take(4)
  elif tag in (5,6):r.take(8);i+=1
  elif tag==7:cp[i]=('class',r.u2())
  elif tag in (8,16,19,20):r.take(2)
  elif tag in (9,10,11,12,17,18):r.take(4)
  elif tag==15:r.take(3)
  else:raise ValueError(f'cp {tag}')
  i+=1
 def utf(i):return cp[i][1]
 r.take(6);r.take(2*r.u2())
 for _ in range(r.u2()):r.take(6);list(scan_bytecode.attrs(r))
 methods=[]
 for _ in range(r.u2()):
  flags=r.u2();name=utf(r.u2());desc=utf(r.u2())
  for attr,data in scan_bytecode.attrs(r):
   if utf(attr)=='Code':
    cr=scan_bytecode.R(data);cr.take(4);cr.take(cr.u4());count=cr.u2();types=[]
    for _ in range(count):
     cr.take(6);idx=cr.u2();types.append(utf(cp[idx][1]) if idx else '*')
    if flags&8 and count and sig.fullmatch(desc) and not name.startswith('<'):methods.append((name,desc,types))
 return methods
items=[];all_types=collections.Counter();classes=0;fail=[];all_candidates=0
with zipfile.ZipFile(jar) as z:
 for file in z.namelist():
  if not file.endswith('.class'):continue
  classes+=1
  try:
   for name,desc,types in parse(z.read(file)):
    all_candidates+=1;all_types.update(types)
    if all(t=='*' or t in allowed or t.startswith('net/minecraft/') for t in types):items.append((file[:-6],name,desc,types))
  except Exception as e:fail.append((file,str(e)))
if fail:raise RuntimeError(f'inventario incompleto {fail[:5]}')
subprocess.run(['cargo','build','--release','--manifest-path',str(root/'Cargo.toml')],check=True)
with tempfile.TemporaryDirectory(prefix='mc-audit-exceptions-') as tmp:
 d=pathlib.Path(tmp)
 def audit(item):
  i,(cls,name,desc,types)=item
  try:
   p=subprocess.run([str(root/'target/release/mc-aot'),'compile',str(jar),cls,name,desc,str(d/f'out-{i}')],capture_output=True,text=True,timeout=45)
   out={'class':cls,'method':name,'descriptor':desc,'handler_types':types,'compiled':p.returncode==0}
   if p.returncode:out['error']=(p.stderr.strip() or p.stdout.strip())[:700]
   return out
  except subprocess.TimeoutExpired:return {'class':cls,'method':name,'descriptor':desc,'handler_types':types,'compiled':False,'error':'timeout tras 45 segundos'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(audit,enumerate(items)))
success=[r for r in results if r['compiled']]
out={'classes_read':classes,'scope':'Métodos static con Code y tabla de manejadores, firmas acotadas; se prueban candidatos con tipos catch incorporados, de Minecraft o catch-all; los tipos de Minecraft solo se admiten si su jerarquía puede resolverse.','signature_candidates_with_handlers':all_candidates,'handler_types_all_signature_candidates':dict(all_types),'candidates_with_supported_catch_types':len(items),'candidate_classes':len({r[0] for r in items}),'compiled_methods':len(success),'classes_with_compiled_method':len({r['class'] for r in success}),'fully_supported_classes_certified':0,'limitations':'Compilación no garantiza equivalencia ni ejecución de inicializadores o clases completas. Tipos incorporados y jerarquías Minecraft verificadas; constructores Minecraft solo triviales y sin estado.','results':results}
report.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(f"{classes} clases leídas; {all_candidates} métodos con handlers y firma acotada; {len(items)} con tipos catch de Minecraft/incorporados o catch-all; {len(success)} compilan en {out['classes_with_compiled_method']} clases; 0 clases completas certificadas. Informe: {report}")
