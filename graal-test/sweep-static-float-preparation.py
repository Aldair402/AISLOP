#!/usr/bin/env python3
"""Lee bits preparados de campos F/D reales en clases sin <clinit>; no prueba operaciones float."""
import base64,hashlib,json,os,pathlib,subprocess,sys,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;sys.path.insert(0,str(root/'mc-aot'));from scan_static_init import parse
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar';inner=root/'downloads/server-26.3-inner.jar';items=[]
with zipfile.ZipFile(inner) as z:
 for file in z.namelist():
  if not file.endswith('.class'):continue
  flags,name,parent,interfaces,fields,methods=parse(z.read(file));st=[(f,n,d) for f,n,d in fields if f&8]
  if parent!='java/lang/Object' or interfaces or flags&0x200 or any(n=='<clinit>' for _,n,_,_ in methods):continue
  if any(f&0x40 or not (d in {'I','J','Z','B','C','S','F','D','[I','[J','[Z','[B','[C','[S','[Ljava/lang/String;'} or (d.startswith('L') and d.endswith(';'))) for f,n,d in st):continue
  ff=[{'name':n,'descriptor':d} for _,n,d in st if d in ('F','D')]
  if ff:items.append({'class':name,'fields':ff})
with tempfile.TemporaryDirectory(prefix='mc-real-float-prep-') as t:
 d=pathlib.Path(t);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'graal-test/StaticReferenceFieldSweep.java')],check=True)
 rows=[(x,f) for x in items for f in x['fields']];inp=''.join(x['class']+'\t'+f['name']+'\n' for x,f in rows)
 p=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'StaticReferenceFieldSweep'],input=inp,capture_output=True,text=True,check=True,timeout=90)
 ref=[line.split('\t',2)[1:] for line in p.stderr.splitlines() if line.startswith('MCRESULT\t')]
 if len(ref)!=len(rows):raise AssertionError(('salida JVM',len(ref),len(rows)))
 refs={};skipped=[]
 for (item,field),(kind,val) in zip(rows,ref):
  if kind=='ERROR':skipped.append({'class':item['class'],'field':field['name'],'error':val});continue
  refs[(item['class'],field['name'])]=base64.b64decode(val).decode()
 compared=0;programs=0;failures=[]
 for i,item in enumerate(items):
  available=[f for f in item['fields'] if (item['class'],f['name']) in refs]
  if not available:continue
  out=d/f'm-{i}';cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','multi-static-demo',str(jar),item['class'],str(out)]
  for f in available:cmd+=['@'+f['name'],f['descriptor']]
  p=subprocess.run(cmd,capture_output=True,text=True)
  if p.returncode:failures.append({'class':item['class'],'error':p.stderr});continue
  native=subprocess.run([str(out),*map(str,range(len(available)))],capture_output=True,text=True,check=True).stdout.splitlines()
  expected=[refs[(item['class'],f['name'])] for f in available]
  if native!=expected:raise AssertionError((item['class'],expected,native))
  compared+=len(available);programs+=1
 report={'candidate_classes_without_clinit':len(items),'fields_candidates':len(rows),'programs_compared':programs,'fields_compared':compared,'jvm_skips':skipped,'compile_failures':failures,'limitations':'Lectura diagnóstica de bits tras preparación; no soporta bytecode ni aritmética float/double. No verifica clases completas.'}
 (root/'analysis/static-float-preparation-sweep.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(f'OK: bits de {compared} campos F/D de {programs}/{len(items)} clases sin <clinit> coinciden con Java 25; {len(skipped)} lecturas omitidas en JVM, {len(failures)} fallos de compilación.')
 if failures:print('Fallos:',failures)
 if skipped:print('Omisiones:',skipped)
