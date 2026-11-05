#!/usr/bin/env python3
"""Muestrea campos estáticos reales String y primitivos frente a Java 25."""
import base64,hashlib,json,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
audit=json.loads((root/'analysis/audit-static-references.json').read_text());items=[x for x in audit['results'] if x['compiled']]
with tempfile.TemporaryDirectory(prefix='mc-static-reference-sweep-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'graal-test/StaticReferenceFieldSweep.java')],check=True)
 inp=''.join(x['class']+'\t'+x['field']['name']+'\n' for x in items)
 p=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'StaticReferenceFieldSweep'],input=inp,capture_output=True,text=True,check=True,timeout=90)
 ref=[line.split('\t',2)[1:] for line in p.stderr.splitlines() if line.startswith('MCRESULT\t')]
 if len(ref)!=len(items):raise AssertionError(('salida JVM',len(ref),len(items)))
 tested=0;strings=0;clinits=0;skipped=[]
 for i,(item,(kind,value)) in enumerate(zip(items,ref)):
  if kind=='ERROR':skipped.append({'class':item['class'],'error':value});continue
  expected=base64.b64decode(value)+b'\n';out=d/f'm-{i}';field=item['field']
  subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','multi-static-demo',str(jar),item['class'],str(out),'@'+field['name'],field['descriptor']],capture_output=True,text=True,check=True)
  native=subprocess.run([str(out),'0'],capture_output=True,check=True).stdout
  if expected!=native:raise AssertionError((item['class'],field,expected[:200],native[:200]))
  tested+=1;strings+=field['descriptor']=='Ljava/lang/String;';clinits+=item['has_clinit']
 summary={'compiled_programs_in_audit':len(items),'programs_compared':tested,'string_fields_compared':strings,'programs_with_clinit_compared':clinits,'skipped_java_errors':skipped,'limitations':'Lee un campo por clase, no verifica todos los campos, arrays, efectos, métodos ni clases completas. Formato stdout es diagnóstico.'}
 (root/'analysis/static-reference-sweep.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(f'OK: {tested}/{len(items)} lecturas de campos coinciden con Java 25; {strings} String, {clinits} programas con <clinit>; {len(skipped)} omitidos por errores JVM')
 if skipped:print('Omitidos:',skipped)
