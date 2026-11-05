#!/usr/bin/env python3
"""Audita un subconjunto experimental de clases para object-demo; no certifica clases completas."""
import concurrent.futures, json, pathlib, subprocess, sys, tempfile, zipfile
from scan_bytecode import parse, instructions
ROOT=pathlib.Path(__file__).resolve().parent
jar=pathlib.Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT.parent/'downloads/server-26.3-inner.jar'
report=pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT.parent/'analysis/audit-objects.json'
subprocess.run(['cargo','build','--release','--manifest-path',str(ROOT/'Cargo.toml')],check=True)
bin=ROOT/'target/release/mc-aot'
# Es un filtro permisivo: el compilador vuelve a validar campos, métodos y referencias.
allowed={0x57,0x59,0x5f,0x10,0x11,0x2a,0x15,0x1b,0x1c,0x1d,*range(0x02,0x09),0xb4,0xb5,0xb7,0x60,0x64,0x68,0xac,0xb1}
candidates=[];scan_errors=[]; total=0
with zipfile.ZipFile(jar) as z:
 for f in z.namelist():
  if not f.endswith('.class'):continue
  total+=1
  try:
   cp,methods=parse(z.read(f))
   ctors=[m for m in methods if m[1]=='<init>']
   if len(ctors)!=1:continue
   desc=ctors[0][2]
   if not desc.startswith('(') or not desc.endswith(')V') or any(c!='I' for c in desc[1:-2]):continue
   if len(methods)<2:continue
   if any(flags & (0x8|0x20|0x100|0x400) for flags,_,_,_ in methods):continue
   if any(name!='<init>' and desc!='()I' for _,name,desc,_ in methods):continue
   if any(any(op not in allowed for _,op,_ in instructions(code)) for _,_,_,code in methods):continue
   candidates.append(f[:-6])
  except Exception as e: scan_errors.append({'class':f,'error':str(e)})
if scan_errors:raise SystemExit(f'Inventario incompleto: {len(scan_errors)} errores')
with tempfile.TemporaryDirectory(prefix='mc-object-audit-') as td:
 d=pathlib.Path(td)
 def task(pair):
  i,name=pair; dest=d/str(i)
  try:
   p=subprocess.run([str(bin),'object-demo',str(jar),name,str(dest)],capture_output=True,text=True,timeout=45)
   return {'class':name,'compiled':p.returncode==0,**({'error':p.stderr.strip()[:500]} if p.returncode else {})}
  except subprocess.TimeoutExpired:return {'class':name,'compiled':False,'error':'timeout'}
  finally:
   dest.unlink(missing_ok=True);pathlib.Path(str(dest)+'.rs').unlink(missing_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(task,enumerate(candidates)))
ok=[r for r in results if r['compiled']]
payload={'classes_scanned':total,'candidate_count':len(candidates),'compiled_object_programs':len(ok),'classes_fully_certified':0,'results':results,'limitations':'Filtro de métodos declarados muy limitado. Una compilación exitosa no valida los métodos heredados ni semántica JVM; no es una clase completa certificada.'}
report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
print(f'{total} clases leídas; {len(candidates)} candidatas por forma; {len(ok)} programas experimentales de instancia compilados')
print('Ninguna clase se certifica completa. Informe:',report)
