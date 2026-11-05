#!/usr/bin/env python3
"""Compara por muestreo los programas de campos e inicialización con Java."""
import hashlib,json,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
audit=json.loads((root/'analysis/audit-static-init.json').read_text());items=[x for x in audit['results'] if x['compiled']]
with tempfile.TemporaryDirectory(prefix='mc-static-sweep-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'graal-test/StaticSweepReference.java')],check=True)
 rows=[x for item in items for x in [item]*4]
 inp=''.join(x['class']+'\t'+x['field']['name']+'\n' for x in rows)
 p=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'StaticSweepReference'],input=inp,capture_output=True,text=True,check=True,timeout=90)
 ref=[line.split('\t',1)[1] for line in p.stderr.splitlines() if line.startswith('MCRESULT\t')]
 if len(ref)!=len(rows):raise AssertionError(('salida JVM',len(ref),len(rows)))
 tested=0;skipped=[]
 for i,item in enumerate(items):
  java=ref[i*4:i*4+4]
  if any(x.startswith('ERROR:') for x in java):skipped.append({'class':item['class'],'errors':java});continue
  out=d/f'm-{i}';field=item['field']
  subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','static-demo',str(jar),item['class'],str(out),'@'+field['name'],field['descriptor']],capture_output=True,text=True,check=True)
  got=subprocess.run([str(out),'0','0','0','0'],capture_output=True,text=True,check=True).stdout.splitlines()
  if java!=got:raise AssertionError((item['class'],field,java,got))
  tested+=1
 summary={'compiled_programs_in_audit':len(items),'programs_compared':tested,'comparisons':tested*4,'skipped_java_errors':skipped,'limitations':'Lee un campo por clase; no verifica todos los campos, métodos, efectos secundarios, excepciones ni clases completas.'}
 (root/'analysis/static-init-sweep.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(f'OK: {tested*4} lecturas; {tested}/{len(items)} programas de inicialización/campos coinciden con Java 25; {len(skipped)} con errores JVM omitidos')
 if skipped:print('Omitidos:',skipped)
