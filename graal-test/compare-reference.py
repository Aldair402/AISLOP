#!/usr/bin/env python3
"""Compara campo de referencia, identidad y null con FeatureFlagUniverse real."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;here=pathlib.Path(__file__).resolve().parent
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar';native=root/'mc-aot/examples/flag-reference'
with tempfile.TemporaryDirectory(prefix='mc-ref-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');p=pathlib.PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts:raise ValueError('ruta insegura')
    raw=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('checksum inválido')
    dst=d/kind/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw);cp.append(str(dst))
 classpath=os.pathsep.join(cp);subprocess.run([str(jdk/'javac'),'-cp',classpath,'-d',str(d),str(here/'ReferenceFieldReference.java')],check=True)
 rng=random.Random(2027);programs=[]
 for _ in range(200):
  cmd=[];types=[] # S = string, N = null, T = destino
  for _ in range(35):
   choices=['string','null']
   str_or_null=[i for i,t in enumerate(types) if t in ('S','N')]
   targets=[i for i,t in enumerate(types) if t=='T']
   strs=[i for i,t in enumerate(types) if t=='S']
   if types:choices+=['copy','eq']
   if str_or_null:choices+=['new','new']
   if targets:choices+=['get','get']
   if strs:choices+=['text']
   op=rng.choice(choices)
   if op=='string':cmd+=['string',rng.choice(['Mundo','Mundo','Arbol','Árbol','村','🚀'])];types.append('S')
   elif op=='null':cmd+=['null'];types.append('N')
   elif op=='copy':
    i=rng.randrange(len(types));cmd+=['copy',str(i)];types.append(types[i])
   elif op=='new':cmd+=['new',str(rng.choice(str_or_null))];types.append('T')
   elif op=='get':
    cmd+=['get',str(rng.choice(targets))]
    # El getter puede devolver String o null; para generar comandos seguros se usa tipo desconocido.
    types.append('U')
   elif op=='eq':cmd+=['eq',str(rng.randrange(len(types))),str(rng.randrange(len(types)))]
   else:cmd+=['text',str(rng.choice(strs))]
  programs.append(cmd)
 programs += [['string','x','string','x','new','0','get','2','eq','0','3','eq','1','3'],['null','new','0','get','1','eq','0','2']]
 proc=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'ReferenceFieldReference'],input=''.join(' '.join(x)+'\n' for x in programs),text=True,capture_output=True,check=True)
 lines=proc.stdout.splitlines()
 if len(lines)!=len(programs):raise RuntimeError('cantidad incorrecta de líneas Java')
 for cmd,expected in zip(programs,lines):
  p=subprocess.run([str(native),*cmd],text=True,capture_output=True)
  if p.returncode!=0 or ','.join(p.stdout.splitlines())!=expected:raise AssertionError((cmd,p.stdout,p.stderr,expected))
 for cmd in [['null','get','0'],['null','text','0']]:
  java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'ReferenceFieldReference'],input=' '.join(cmd)+'\n',text=True,capture_output=True,check=True)
  p=subprocess.run([str(native),*cmd],text=True,capture_output=True)
  if java.stdout.strip()!='0,ERR_NULL' or p.returncode!=2 or p.stdout.strip()!='0' or 'NullPointerException' not in p.stderr:raise AssertionError((cmd,java.stdout,p.stdout,p.stderr))
 print(f'OK: {len(programs)} secuencias, {sum(len(x) for x in programs)} tokens; campo String, identidad y null coinciden en las pruebas')
