#!/usr/bin/env python3
"""Barrido acotado de candidatos de arrays; omite MapItem sin bootstrap de registros."""
import hashlib,json,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
audit=json.loads((root/'analysis/audit-arrays.json').read_text());allitems=[r for r in audit['results'] if r['compiled']]
skipped=[r for r in allitems if r['class']=='net/minecraft/world/item/MapItem'];items=[r for r in allitems if r not in skipped]
if not items:raise SystemExit('Ejecuta primero mc-aot/audit-arrays.py')
with tempfile.TemporaryDirectory(prefix='mc-array-sweep-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'graal-test/ArraySweepReference.java')],check=True)
 lengths=[None,0,1,4,16,256,1024,4096];ints=[-1,0,1,3,4,15,255,256,1023,1024,2147483647,-2147483648]
 def kinds(desc):
  raw=desc[1:desc.index(')')];p=0;types=[]
  while p<len(raw):
   if raw[p]=='[':types.append(raw[p:p+2]);p+=2
   else:types.append(raw[p]);p+=1
  return types
 def val(t,n,j):
  if t[0]=='[':
   length=lengths[(n+j)%len(lengths)]
   if length is None:return 'null'
   k=t[1];data=[(x*13+7)%256-128 if k=='B' else (x%2 if k=='Z' else (x*251+17)%32767) for x in range(length)]
   return '['+','.join(map(str,data))+']'
  if t=='Z':return str((n+j)%2)
  if t=='B':return str((n+j)%256-128)
  if t=='C':return str((n+j)%65536)
  if t=='S':return str((n+j)%65536-32768)
  return str(ints[(n*5+j*3)%len(ints)])
 rows=[]
 for idx,item in enumerate(items):
  types=kinds(item['descriptor'])
  for n in range(24):rows.append((idx,[val(t,n,idx+j) for j,t in enumerate(types)]))
 inp=''.join('\t'.join([items[i]['class'],items[i]['method'],items[i]['descriptor'],'|'.join(args)])+'\n' for i,args in rows)
 proc=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'ArraySweepReference'],input=inp,capture_output=True,text=True,check=True,timeout=90)
 expected=[x.split('\t',1)[1] for x in proc.stderr.splitlines() if x.startswith('MCRESULT\t')]
 if len(expected)!=len(rows):raise AssertionError(('respuestas JVM',len(expected),len(rows),proc.stderr[-3000:]))
 binaries={};tested=set();counts={}
 for (idx,args),want in zip(rows,expected):
  r=items[idx];key=f"{r['class']}.{r['method']}{r['descriptor']}"
  if idx not in binaries:
   out=d/f'm-{idx}';subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(jar),r['class'],r['method'],r['descriptor'],str(out)],capture_output=True,text=True,check=True);binaries[idx]=out
  n=subprocess.run([str(binaries[idx]),*args],capture_output=True,text=True,timeout=5)
  if want.startswith('ERROR:'):
   category=want[6:];counts[category]=counts.get(category,0)+1
   if n.returncode==0 or category not in n.stderr:raise AssertionError((key,args[:1],want,n.returncode,n.stdout,n.stderr))
  elif n.returncode or n.stdout.strip()!=want:raise AssertionError((key,args[:1],want,n.returncode,n.stdout,n.stderr))
  tested.add(idx)
 summary={'audit_compiled_methods':len(allitems),'compared_methods':len(tested),'comparisons':len(rows),'java_errors_compared_by_category':counts,'skipped':[{'class':r['class'],'method':r['method'],'descriptor':r['descriptor'],'reason':'MapItem requiere bootstrap de registros para inicializar la clase; no se hizo en esta prueba.'} for r in skipped],'limitations':'Muestras acotadas; diferencias de inicialización y excepciones no capturables; no certifica clases completas.'}
 (root/'analysis/array-sweep.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(f"OK: {len(rows)} resultados en {len(tested)}/{len(allitems)} métodos de arrays coinciden con Java 25; {len(skipped)} omitido por requerir bootstrap")
