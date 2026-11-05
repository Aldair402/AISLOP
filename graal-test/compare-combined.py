#!/usr/bin/env python3
"""Compara un heap mixto: interfaces, identidad y campos de referencia en clases reales."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;here=pathlib.Path(__file__).resolve().parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
jar=root/'downloads/server-26.3.jar';native=root/'mc-aot/examples/combined-heap'
with tempfile.TemporaryDirectory(prefix='mc-mixed-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');p=pathlib.PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts:raise ValueError('ruta insegura')
    raw=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('checksum inválido')
    target=d/kind/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);cp.append(str(target))
 classpath=os.pathsep.join(cp);subprocess.run([str(jdk/'javac'),'-cp',classpath,'-d',str(d),str(here/'MultiReference.java')],check=True)
 rng=random.Random(963);programs=[]
 for _ in range(200):
  cmd=[];slots=[]
  # Las tuplas F contienen el tipo de su campo; solo orientan al generador de pruebas.
  for _ in range(40):
   choices=['new0','new1','string','null']
   if slots:choices+=['copy','eq']
   strings=[i for i,t in enumerate(slots) if t=='S'];strnull=[i for i,t in enumerate(slots) if t in ('S','N')]
   heights=[i for i,t in enumerate(slots) if t=='H'];flags=[i for i,t in enumerate(slots) if isinstance(t,tuple)]
   if strnull:choices+=['newref']
   if flags:choices+=['getref','getref']
   if strings:choices+=['text']
   if heights:choices+=['call','call']
   op=rng.choice(choices)
   if op=='new0':cmd+=['new','0',str(rng.randint(-2147483648,2147483647)),str(rng.randint(-2147483648,2147483647))];slots.append('H')
   elif op=='new1':cmd+=['new','1'];slots.append('H')
   elif op=='string':cmd+=['string',rng.choice(['Alpha','Alpha','Árbol','村','🚀'])];slots.append('S')
   elif op=='null':cmd+=['null'];slots.append('N')
   elif op=='copy':i=rng.randrange(len(slots));cmd+=['copy',str(i)];slots.append(slots[i])
   elif op=='eq':cmd+=['eq',str(rng.randrange(len(slots))),str(rng.randrange(len(slots)))]
   elif op=='newref':i=rng.choice(strnull);cmd+=['newref',str(i)];slots.append(('F',slots[i]))
   elif op=='getref':i=rng.choice(flags);cmd+=['getref',str(i)];slots.append(slots[i][1])
   elif op=='text':cmd+=['text',str(rng.choice(strings))]
   else:cmd+=['call',str(rng.choice(heights)),rng.choice(['getHeight','getMinY','getMaxY'])]
  programs.append(cmd)
 programs += [['new','0','384','-64','new','1','string','Mundo','newref','2','getref','3','eq','2','4','text','4','call','0','getMaxY','call','1','getMaxY']]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'MultiReference'],input=''.join(' '.join(p)+'\n' for p in programs),text=True,capture_output=True,check=True)
 lines=java.stdout.splitlines()
 if len(lines)!=len(programs):raise RuntimeError('Java devolvió cantidad incorrecta de resultados')
 for cmd,expect in zip(programs,lines):
  p=subprocess.run([str(native),*cmd],text=True,capture_output=True)
  if p.returncode!=0 or ','.join(p.stdout.splitlines())!=expect:raise AssertionError((cmd,p.stdout,p.stderr,expect))
 for cmd in [['null','getref','0'],['null','text','0'],['null','call','0','getHeight']]:
  j=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'MultiReference'],input=' '.join(cmd)+'\n',text=True,capture_output=True,check=True)
  p=subprocess.run([str(native),*cmd],text=True,capture_output=True)
  if j.stdout.strip()!='0,ERR_NULL' or p.returncode!=2 or p.stdout.strip()!='0' or 'NullPointerException' not in p.stderr:raise AssertionError((cmd,j.stdout,p.stdout,p.stderr))
 print(f'OK: {len(programs)} secuencias mixtas y 3 categorías null coinciden con Java 25')
