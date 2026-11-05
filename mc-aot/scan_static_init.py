#!/usr/bin/env python3
"""Inventario de clases candidatas al experimento static-demo; no es certificación."""
import json,pathlib,re,zipfile
import scan_bytecode as s
ROOT=pathlib.Path(__file__).resolve().parent;JAR=ROOT.parent/'downloads/server-26.3-inner.jar'
SIG=re.compile(r'^\((?:\[?[IJZBCS])*\)[IJZBCSJV]$')
def parse(data):
 r=s.R(data)
 if r.u4()!=0xcafebabe:raise ValueError('magic')
 r.take(4);n=r.u2();cp=[None]*n;i=1
 while i<n:
  t=r.u1()
  if t==1:cp[i]=('utf',r.take(r.u2()).decode('utf8','replace'))
  elif t in (3,4):r.take(4)
  elif t in (5,6):r.take(8);i+=1
  elif t==7:cp[i]=('class',r.u2())
  elif t in (8,16,19,20):r.take(2)
  elif t in (9,10,11,12,17,18):r.take(4)
  elif t==15:r.take(3)
  else:raise ValueError(f'CP tag {t}')
  i+=1
 def utf(i):return cp[i][1]
 def cname(i):return utf(cp[i][1]) if i else None
 flags=r.u2();name=cname(r.u2());parent=cname(r.u2());interfaces=[cname(r.u2()) for _ in range(r.u2())];fields=[]
 for _ in range(r.u2()):
  ff=r.u2();fn=utf(r.u2());fd=utf(r.u2());list(s.attrs(r));fields.append((ff,fn,fd))
 methods=[]
 for _ in range(r.u2()):
  mf=r.u2();mn=utf(r.u2());md=utf(r.u2());code=None
  for a,data in s.attrs(r):
   if utf(a)=='Code':
    sub=s.R(data);sub.take(4);code=sub.take(sub.u4())
  methods.append((mf,mn,md,code))
 return flags,name,parent,interfaces,fields,methods

def find_candidates(jar=JAR):
 classes=[];failures=[]
 with zipfile.ZipFile(jar) as z:
  for file in z.namelist():
   if not file.endswith('.class'):continue
   try:
    flags,name,parent,interfaces,fields,methods=parse(z.read(file))
    static=[(f,n,d) for f,n,d in fields if f&8]
    if parent!='java/lang/Object' or interfaces or flags&0x0200 or not static:continue
    if any(f&0x0040 or d not in 'IJZBCS' or len(d)!=1 for f,n,d in static):continue
    candidates=[{'method':n,'descriptor':d} for f,n,d,c in methods if f&8 and not n.startswith('<') and SIG.fullmatch(d) and c is not None]
    if not candidates:continue
    clinit=next((c for f,n,d,c in methods if n=='<clinit>' and d=='()V'),None)
    ops=[s.NAMES[o] for _,o,_ in s.instructions(clinit)] if clinit else []
    classes.append({'class':name,'static_fields':len(static),'field_details':[{'name':n,'descriptor':d} for _,n,d in static],'has_clinit':clinit is not None,'clinit_instructions':ops,'candidate_methods':candidates})
   except Exception as e:failures.append((file,str(e)))
 if failures:raise RuntimeError(f'Errores de lectura: {failures[:10]}')
 return classes
if __name__=='__main__':
 items=find_candidates();report={'scope':'Clases directas de Object, sin interfaces, con campos estáticos I/J/Z/B/C/S no volatile y al menos un método static de firma admitida. Filtro de forma, no verifica inicialización ni compatibilidad.','classes':len(items),'classes_with_clinit':sum(x['has_clinit'] for x in items),'methods':sum(len(x['candidate_methods']) for x in items),'results':items}
 (ROOT.parent/'analysis/static-init-inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(f"Candidatos por forma: {report['classes']} clases, {report['classes_with_clinit']} con <clinit>, {report['methods']} métodos. No es traducción.")
 for x in items[:50]:print(x['class'],x['static_fields'],x['candidate_methods'][:3],','.join(x['clinit_instructions'][:15]))
