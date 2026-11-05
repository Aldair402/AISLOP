#!/usr/bin/env python3
"""Audita compilación del experimento de inicialización por clase; no certifica clases completas."""
import concurrent.futures,json,pathlib,subprocess,tempfile
from scan_static_init import find_candidates
root=pathlib.Path(__file__).resolve().parent;jar=root.parent/'downloads/server-26.3-inner.jar';report=root.parent/'analysis/audit-static-init.json'
subprocess.run(['cargo','build','--release','--manifest-path',str(root/'Cargo.toml')],check=True)
items=find_candidates(jar)
with tempfile.TemporaryDirectory(prefix='mc-audit-static-init-') as tmp:
 d=pathlib.Path(tmp)
 def audit(pair):
  i,item=pair;field=item['field_details'][0];out=d/f'out-{i}'
  cmd=[str(root/'target/release/mc-aot'),'static-demo',str(jar),item['class'],str(out),'@'+field['name'],field['descriptor']]
  try:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
   r={'class':item['class'],'has_clinit':item['has_clinit'],'field':field,'compiled':p.returncode==0}
   if p.returncode:r['error']=(p.stderr.strip() or p.stdout.strip())[:700]
   return r
  except subprocess.TimeoutExpired:return {'class':item['class'],'has_clinit':item['has_clinit'],'field':field,'compiled':False,'error':'timeout tras 45 segundos'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(audit,enumerate(items)))
success=[x for x in results if x['compiled']]
summary={'scope':'Un programa static-demo por clase con al menos un campo estático primitivo; clases directas de Object sin interfaces y sin otros campos estáticos. Lee un campo y compila <clinit> si existe. No incluye métodos de instancia ni todas las operaciones de la clase.','candidate_classes':len(items),'candidates_with_clinit':sum(x['has_clinit'] for x in items),'compiled_programs':len(success),'compiled_programs_with_clinit':sum(x['has_clinit'] for x in success),'fully_supported_classes_certified':0,'limitations':'Compilación aislada no prueba equivalencia; clase completa no traducida. Se omiten sincronización, excepciones, herencia y múltiples clases con inicializadores.','results':results}
report.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(f"Candidatas: {len(items)} clases ({summary['candidates_with_clinit']} con <clinit>); programas compilados: {len(success)} ({summary['compiled_programs_with_clinit']} con <clinit>); 0 clases completas certificadas. Informe: {report}")
