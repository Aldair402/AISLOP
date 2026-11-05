#!/usr/bin/env python3
"""Audita compilación del experimento de inicialización por clase; no certifica clases completas."""
import concurrent.futures,json,pathlib,subprocess,tempfile,zipfile
from scan_static_init import parse
root=pathlib.Path(__file__).resolve().parent;jar=root.parent/'downloads/server-26.3-inner.jar';report=root.parent/'analysis/audit-multi-static.json'
subprocess.run(['cargo','build','--release','--manifest-path',str(root/'Cargo.toml')],check=True)
items=[]
with zipfile.ZipFile(jar) as z:
 for file in z.namelist():
  if not file.endswith('.class'):continue
  flags,name,parent,interfaces,fields,methods=parse(z.read(file))
  static=[(f,n,d) for f,n,d in fields if f&8]
  if parent!='java/lang/Object' or interfaces or flags&0x0200 or not static:continue
  if any(f&0x40 or len(d)!=1 or d not in 'IJZBCS' for f,n,d in static):continue
  items.append({'class':name,'has_clinit':any(n=='<clinit>' and d=='()V' for _,n,d,_ in methods),'field_details':[{'name':n,'descriptor':d} for _,n,d in static]})
with tempfile.TemporaryDirectory(prefix='mc-audit-multi-static-') as tmp:
 d=pathlib.Path(tmp)
 def audit(pair):
  i,item=pair;field=item['field_details'][0];out=d/f'out-{i}'
  cmd=[str(root/'target/release/mc-aot'),'multi-static-demo',str(jar),item['class'],str(out),'@'+field['name'],field['descriptor']]
  try:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
   r={'class':item['class'],'has_clinit':item['has_clinit'],'field':field,'compiled':p.returncode==0}
   if p.returncode:r['error']=(p.stderr.strip() or p.stdout.strip())[:700]
   return r
  except subprocess.TimeoutExpired:return {'class':item['class'],'has_clinit':item['has_clinit'],'field':field,'compiled':False,'error':'timeout tras 45 segundos'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(audit,enumerate(items)))
success=[x for x in results if x['compiled']]
summary={'scope':'Un programa multi-static-demo por clase con al menos un campo estático primitivo; clases directas de Object sin interfaces y sin otros campos estáticos. Incluye clases sin métodos static admisibles. Lee un campo y compila <clinit> si existe. No incluye métodos de instancia ni todas las operaciones.','candidate_classes':len(items),'candidates_with_clinit':sum(x['has_clinit'] for x in items),'compiled_programs':len(success),'compiled_programs_with_clinit':sum(x['has_clinit'] for x in success),'fully_supported_classes_certified':0,'limitations':'Compilación aislada no prueba equivalencia; clase completa no traducida. Se omiten sincronización, captura de excepciones de inicialización y herencia. Cubre solo campos estáticos primitivos y clases sin interfaces.','results':results}
report.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(f"Candidatas: {len(items)} clases ({summary['candidates_with_clinit']} con <clinit>); programas compilados: {len(success)} ({summary['compiled_programs_with_clinit']} con <clinit>); 0 clases completas certificadas. Informe: {report}")
