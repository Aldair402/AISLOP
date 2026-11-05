#!/usr/bin/env python3
"""Compara identidad, null y despacho entre dos clases reales de Minecraft."""
import hashlib, os, pathlib, random, subprocess, tempfile, zipfile
root=pathlib.Path(__file__).resolve().parent.parent
here=pathlib.Path(__file__).resolve().parent
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
jar=root/'downloads/server-26.3.jar';native=root/'mc-aot/examples/height-heap'
with tempfile.TemporaryDirectory(prefix='mc-multi-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');p=pathlib.PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts:raise ValueError('ruta insegura')
    raw=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('checksum inválido')
    dest=d/kind/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);cp.append(str(dest))
 classpath=os.pathsep.join(cp)
 subprocess.run([str(jdk/'javac'),'-cp',classpath,'-d',str(d),str(here/'MultiReference.java')],check=True)
 rng=random.Random(451);programs=[]
 for case in range(200):
  cmd=[];refs=[]
  # También se crean objetos con iguales campos: igualdad se comprueba por identidad, no valor.
  for _ in range(32):
   choices=['new0','new1','null']
   if refs:choices += ['copy','eq']
   live=[i for i,is_live in enumerate(refs) if is_live]
   if live:choices += ['call','call','call']
   op=rng.choice(choices)
   if op=='new0':
    a=rng.choice([-2147483648,-64,0,384,2147483647,rng.randint(-1000,1000)])
    b=rng.choice([-2147483648,-64,0,2147483647,rng.randint(-1000,1000)])
    cmd += ['new','0',str(a),str(b)];refs.append(True)
   elif op=='new1':cmd+=['new','1'];refs.append(True)
   elif op=='null':cmd+=['null'];refs.append(False)
   elif op=='copy':
    idx=rng.randrange(len(refs));cmd+=['copy',str(idx)];refs.append(refs[idx])
   elif op=='eq':cmd+=['eq',str(rng.randrange(len(refs))),str(rng.randrange(len(refs)))]
   else:cmd+=['call',str(rng.choice(live)),rng.choice(['getHeight','getMinY','getMaxY'])]
  programs.append(cmd)
 programs += [['new','0','384','-64','new','0','384','-64','copy','0','eq','0','1','eq','0','2','call','0','getMaxY'],['null','copy','0','eq','0','1']]
 proc=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'MultiReference'],input=''.join(' '.join(x)+'\n' for x in programs),capture_output=True,text=True,check=True)
 lines=proc.stdout.splitlines()
 if len(lines)!=len(programs):raise RuntimeError('cantidad de líneas JVM inesperada')
 for program,expected in zip(programs,lines):
  out=subprocess.run([str(native),*program],capture_output=True,text=True)
  if out.returncode!=0 or ','.join(out.stdout.splitlines())!=expected:raise AssertionError((program,out.stdout,out.stderr,expected))
 nullref=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'MultiReference'],input='null call 0 getHeight\n',capture_output=True,text=True,check=True)
 result=subprocess.run([str(native),'null','call','0','getHeight'],capture_output=True,text=True)
 if nullref.stdout.strip()!='0,ERR_NULL' or result.returncode!=2 or result.stdout.strip()!='0' or 'NullPointerException' not in result.stderr:raise AssertionError('categoría de error null distinta')
 print(f'OK: {len(programs)} secuencias y {sum(len(x) for x in programs)} tokens de operaciones; identidad, null y despacho coinciden en las pruebas')
