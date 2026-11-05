#!/usr/bin/env python3
"""Contrasta métodos long que compilan (auditoría) con Java; no certifica clases."""
import hashlib,json,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
audit=json.loads((root/'analysis/audit-long.json').read_text());items=[r for r in audit['results'] if r['compiled']]
if not items:raise SystemExit('Ejecuta primero mc-aot/audit-long.py')
with tempfile.TemporaryDirectory(prefix='mc-long-sweep-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'graal-test/LongSweepReference.java')],check=True)
 rng=random.Random(5821);longs=[-(1<<63),-(1<<63)+1,-4294967296,-2147483648,-1,0,1,2,2147483647,4294967295,(1<<63)-1]+[rng.randint(-(1<<63),(1<<63)-1) for _ in range(12)]
 ints=[-(1<<31),-65536,-1000,-33,-1,0,1,2,31,64,65535,(1<<31)-1]+[rng.randint(-(1<<31),(1<<31)-1) for _ in range(12)]
 values={'J':longs,'I':ints,'Z':[0,1],'B':[-128,-1,0,1,127],'S':[-32768,-1,0,1,32767],'C':[0,1,65,65535]}
 rows=[]
 for idx,item in enumerate(items):
  for i in range(24):
   raw=item['descriptor'][1:item['descriptor'].index(')')]
   args=[values[t][(i*(2*j+1)+j*3)%len(values[t])] for j,t in enumerate(raw)]
   rows.append((idx,args))
 inp=''.join('\t'.join([items[idx]['class'],items[idx]['method'],items[idx]['descriptor'],','.join(map(str,args))])+'\n' for idx,args in rows)
 p=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'LongSweepReference'],input=inp,capture_output=True,text=True,check=True,timeout=90)
 ref=[line.split('\t',1)[1] for line in p.stderr.splitlines() if line.startswith('MCRESULT\t')]
 if len(ref)!=len(rows):raise AssertionError(('respuestas JVM',len(ref),len(rows),p.stderr[-3000:]))
 binaries={};tested=set();skipped={};comparisons=0;arithmetic=0
 for (idx,args),expected in zip(rows,ref):
  item=items[idx];key=f"{item['class']}.{item['method']}{item['descriptor']}"
  if expected.startswith('ERROR:') and expected!='ERROR:java.lang.ArithmeticException':skipped[key]=expected;continue
  if idx not in binaries:
   b=d/f'native-{idx}';cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(jar),item['class'],item['method'],item['descriptor'],str(b)]
   subprocess.run(cmd,capture_output=True,text=True,check=True);binaries[idx]=b
  native=subprocess.run([str(binaries[idx]),*map(str,args)],capture_output=True,text=True,timeout=5)
  if expected=='ERROR:java.lang.ArithmeticException':
   if native.returncode==0 or 'ArithmeticException' not in native.stderr:raise AssertionError((key,args,expected,native.returncode,native.stdout,native.stderr))
   arithmetic+=1
  elif native.returncode or native.stdout.strip()!=expected:raise AssertionError((key,args,expected,native.returncode,native.stdout,native.stderr))
  tested.add(idx);comparisons+=1
 summary={'compiled_methods_in_audit':len(items),'methods_compared':len(tested),'comparisons':comparisons,'arithmetic_errors_compared_by_category':arithmetic,'skipped_java_errors':skipped,'limitations':'Muestras acotadas de métodos compilados; errores aritméticos por categoría, no excepciones capturables. No prueba inicialización equivalente, métodos excluidos ni clases completas.'}
 (root/'analysis/long-sweep.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
 print(f"OK: {comparisons} resultados de {len(tested)}/{len(items)} métodos long compilados coinciden con Java 25; errores aritméticos por categoría; {len(skipped)} métodos con errores JVM no comparados en esas muestras")
 if skipped: print('Errores JVM omitidos:',json.dumps(skipped,ensure_ascii=False))
