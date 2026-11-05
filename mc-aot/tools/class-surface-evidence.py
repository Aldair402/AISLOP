#!/usr/bin/env python3
"""Audita un inventario de evidencias parciales; NO certifica clases ni semántica."""
import argparse,hashlib,json,pathlib,re,subprocess,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[2]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def error(text):raise ValueError(text)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('manifest',type=pathlib.Path);ap.add_argument('--jar',type=pathlib.Path,default=root/'downloads/server-26.3-inner.jar');a=ap.parse_args()
 data=json.loads(a.manifest.read_text(encoding='utf-8'))
 # `members_classification` es opcional y solo puede clasificar; no certifica nada.
 allowed_keys={'schema','jar_sha256','class','class_sha256','members','limitations','members_classification'}
 if not set(data)<=allowed_keys or not {'schema','jar_sha256','class','class_sha256','members','limitations'}<=set(data) or data['schema']!='partial-surface-v1':error('esquema de manifiesto inválido; no se permiten afirmaciones de certificación')
 if 'certified' in data or data.get('schema')!='partial-surface-v1':error('no se permiten afirmaciones de certificación')
 if sha(a.jar)!=data['jar_sha256']:error('hash de JAR no coincide')
 name=data['class']
 if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_/$]+',name):error('nombre de clase fuera del perfil')
 with zipfile.ZipFile(a.jar) as z:
  names=[i.filename for i in z.infolist() if i.filename.endswith('.class')]
  if len(names)!=len(set(names)):error('JAR contiene clases duplicadas')
  entry=name+'.class'
  if entry not in names:error('clase ausente del JAR')
  if hashlib.sha256(z.read(entry)).hexdigest()!=data['class_sha256']:error('hash de clase no coincide')
  total=len(names)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','inspect',str(a.jar),name]
 p=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
 if p.returncode:error('inspect falló: '+p.stderr[-2000:])
 surface={'field':set(),'method':set()};expected={};section=None
 for line in p.stdout.splitlines():
  if (m:=re.fullmatch(r'Campos \((\d+)\):',line)):section='field';expected[section]=int(m.group(1));continue
  if (m:=re.fullmatch(r'Métodos \((\d+)\):',line)):section='method';expected[section]=int(m.group(1));continue
  m=re.fullmatch(r'  0x[0-9a-f]{4} (.+)',line)
  if not m or not section:continue
  value=m.group(1).split(' | ',1)[0]
  if section=='field':
   parts=value.split(' ',1)
   if len(parts)!=2:error('línea de campo inesperada')
   key=(parts[0],parts[1])
  else:
   idx=value.find('(')
   if idx<1:error('línea de método inesperada')
   key=(value[:idx],value[idx:])
  if key in surface[section]:error('miembro duplicado')
  surface[section].add(key)
 if set(expected)!={'field','method'} or any(len(surface[k])!=expected[k] for k in surface):error('salida inspect incompleta o incompatible')
 recorded={'field':set(),'method':set()};files={}
 if not isinstance(data['members'],list) or not isinstance(data['limitations'],list) or not data['limitations']:error('miembros o limitaciones inválidos')
 for item in data['members']:
  if set(item)!={'kind','name','descriptor','evidence'}:error('registro de miembro inválido')
  kind=item['kind'];key=(item['name'],item['descriptor'])
  if kind not in surface or key not in surface[kind]:error(f'miembro no declarado: {kind} {key}')
  if key in recorded[kind]:error(f'miembro duplicado en manifiesto: {kind} {key}')
  if not isinstance(item['evidence'],list) or not item['evidence']:error('miembro sin evidencia')
  for evidence in item['evidence']:
   if set(evidence)!={'path','sha256'}:error('registro de evidencia inválido')
   path=(root/evidence['path']).resolve()
   if not path.is_relative_to(root.resolve()) or not path.is_file():error('evidencia fuera del workspace o ausente')
   actual=sha(path)
   if actual!=evidence['sha256']:error('hash de evidencia no coincide: '+evidence['path'])
   files[evidence['path']]=actual
  recorded[kind].add(key)
 # El manifiesto declara evidencia por miembro; el auditor comprueba que esa clasificación
 # cubra exactamente la superficie declarada y la devuelve para que quien la consuma no
 # tenga que inferirla. Sin esto, "sin evidencia" y "solo medida en Java" se confunden.
 classification=data.get('members_classification')
 if classification is not None:
  allowed={'differential','java-only'}
  differential={m for m,k in classification.items() if k=='differential'}
  java_only={m for m,k in classification.items() if k=='java-only'}
  unknown={m for m,k in classification.items() if k not in allowed}
  if unknown:error('clasificación de evidencia desconocida: '+', '.join(sorted(unknown)))
  declared={n+d for n,d in surface['method']}|{n+':'+d for n,d in surface['field']}
  if not set(classification)<=declared:error('clasificación menciona miembros no declarados')
  classified_methods={m for m in classification if ':' not in m}
  classified_fields={m for m in classification if ':' in m}
  reported_methods={n+d for n,d in surface['method']} & classified_methods
  reported_fields={n+':'+d for n,d in surface['field']} & classified_fields
  classification_summary={'differential':sorted(differential),'java_only':sorted(java_only),
   'unclassified_methods':sorted({n+d for n,d in surface['method']}-classified_methods),
   'unclassified_fields':sorted({n+':'+d for n,d in surface['field']}-classified_fields)}
 else:
  classification_summary=None
 result={'class':name,'jar_sha256':data['jar_sha256'],'class_sha256':data['class_sha256'],'classes_in_jar':total,
  'methods_with_partial_evidence':len(recorded['method']),'methods_declared':len(surface['method']),
  'fields_with_partial_evidence':len(recorded['field']),'fields_declared':len(surface['field']),
  'methods_without_evidence':[n+d for n,d in sorted(surface['method']-recorded['method'])],
  'fields_without_evidence':[n+' '+d for n,d in sorted(surface['field']-recorded['field'])],
  'evidence_files':files,'limitations':data['limitations'],'certified':False,
  'evidence_classification':classification_summary,
  'warning':'Inventario de evidencias parciales, no verifica corrección de resultados ni certifica clases.'}
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except (ValueError,OSError,KeyError,TypeError,zipfile.BadZipFile,subprocess.TimeoutExpired) as e:print('ERROR:',e,file=sys.stderr);sys.exit(2)
