#!/usr/bin/env python3
"""Audita compilación de firmas estáticas con String y String[]."""
import concurrent.futures,json,pathlib,re,subprocess,tempfile,zipfile
import scan_bytecode
root=pathlib.Path(__file__).resolve().parent;jar=root.parent/'downloads/server-26.3-inner.jar';report=root.parent/'analysis/audit-strings.json'
subprocess.run(['cargo','build','--release','--manifest-path',str(root/'Cargo.toml')],check=True)
sig=re.compile(r'^\((?:(?:\[?Ljava/lang/String;)|\[?[IJZBCS])*\)(?:[IJZBCSJV]|Ljava/lang/String;)$');items=[];failures=[];count=0
with zipfile.ZipFile(jar) as z:
 for file in z.namelist():
  if not file.endswith('.class'):continue
  count+=1
  try:
   _,methods=scan_bytecode.parse(z.read(file))
   for flags,name,desc,code in methods:
    if flags&8 and 'Ljava/lang/String;' in desc and sig.fullmatch(desc):items.append((file[:-6],name,desc))
  except Exception as e:failures.append((file,str(e)))
if failures:raise RuntimeError(f'Inventario incompleto: {failures[:10]}')
with tempfile.TemporaryDirectory(prefix='mc-audit-strings-') as tmp:
 d=pathlib.Path(tmp)
 def audit(item):
  i,(cls,name,desc)=item
  try:
   p=subprocess.run([str(root/'target/release/mc-aot'),'compile',str(jar),cls,name,desc,str(d/f'out-{i}')],capture_output=True,text=True,timeout=45)
   result={'class':cls,'method':name,'descriptor':desc,'compiled':p.returncode==0}
   if p.returncode:result['error']=(p.stderr.strip() or p.stdout.strip())[:700]
   return result
  except subprocess.TimeoutExpired:return {'class':cls,'method':name,'descriptor':desc,'compiled':False,'error':'timeout tras 45 segundos'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(audit,enumerate(items)))
success=[r for r in results if r['compiled']]
summary={'classes_read':count,'scope':'Métodos static con String o String[] en la firma y argumentos limitados a estos, primitivas o arrays primitivos; retorno primitivo, void o String.','candidates':len(items),'candidate_classes':len({r[0] for r in items}),'compiled_methods':len(success),'classes_with_at_least_one_compiled_method':len({r['class'] for r in success}),'fully_supported_classes_certified':0,'limitations':'Compilar no demuestra equivalencia, inicializadores, excepciones capturables ni clases completas. Heap limitado sin GC.','results':results}
report.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(f"{count} clases leídas; candidatos String: {len(items)} en {summary['candidate_classes']} clases; compilan {len(success)} en {summary['classes_with_at_least_one_compiled_method']} clases; 0 clases completas certificadas. Informe: {report}")
