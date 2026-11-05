#!/usr/bin/env python3
"""Busca constructor (String) y getter String simples; no certifica clases completas."""
import concurrent.futures,json,pathlib,subprocess,sys,tempfile,zipfile
from scan_bytecode import parse,instructions
ROOT=pathlib.Path(__file__).resolve().parent
jar=pathlib.Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT.parent/'downloads/server-26.3-inner.jar'
report=pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT.parent/'analysis/audit-references.json'
subprocess.run(['cargo','build','--release','--manifest-path',str(ROOT/'Cargo.toml')],check=True)
bin=ROOT/'target/release/mc-aot';candidates=[];errors=[];classes=0
with zipfile.ZipFile(jar) as z:
 for f in z.namelist():
  if not f.endswith('.class'):continue
  classes+=1
  try:
   cp,ms=parse(z.read(f));ctors=[m for m in ms if m[1]=='<init>' and m[2]=='(Ljava/lang/String;)V'];gets=[m for m in ms if m[2]=='()Ljava/lang/String;']
   if any(n=='<clinit>' for _,n,_,_ in ms):continue
   for ctor in ctors:
    if any(op not in {0x2a,0x2b,0x01,0x59,0xb7,0xb4,0xb5,0xb1} for _,op,_ in instructions(ctor[3])):continue
    for getter in gets:
     if any(op not in {0x2a,0x01,0x59,0xb4,0xb0} for _,op,_ in instructions(getter[3])):continue
     candidates.append((f[:-6],getter[1]))
  except Exception as e:errors.append({'class':f,'error':str(e)})
if errors:raise SystemExit(f'Inventario incompleto: {len(errors)} errores')
with tempfile.TemporaryDirectory(prefix='mc-ref-audit-') as tmp:
 d=pathlib.Path(tmp)
 def task(item):
  i,(name,getter)=item;dest=d/str(i)
  try:
   p=subprocess.run([str(bin),'reference-demo',str(jar),name,getter,str(dest)],capture_output=True,text=True,timeout=45)
   return {'class':name,'getter':getter,'compiled':p.returncode==0,**({'error':p.stderr.strip()[:500]} if p.returncode else {})}
  except subprocess.TimeoutExpired:return {'class':name,'getter':getter,'compiled':False,'error':'timeout'}
  finally:dest.unlink(missing_ok=True);pathlib.Path(str(dest)+'.rs').unlink(missing_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(task,enumerate(candidates)))
ok=[x for x in results if x['compiled']]
payload={'classes_scanned':classes,'candidate_method_pairs':len(candidates),'compiled_method_pairs':len(ok),'classes_with_pair_compiled':len({x['class'] for x in ok}),'classes_fully_certified':0,'results':results,'limitations':'Solo constructor(String) y getter String específicos. Compilar no valida comportamiento ni clase completa. No se ejecutan inicializadores, métodos restantes ni semántica general de String.'}
report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
print(f'{classes} clases, {len(candidates)} pares candidatos, {len(ok)} pares compilan en {payload["classes_with_pair_compiled"]} clases; ninguna clase completa certificada.')
print('Informe:',report)
