#!/usr/bin/env python3
"""Compara constructor y getter para todos los pares aceptados por audit-references.py."""
import hashlib,json,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;here=pathlib.Path(__file__).resolve().parent
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
report=json.loads((root/'analysis/audit-references.json').read_text());methods=[r for r in report['results'] if r['compiled']]
with tempfile.TemporaryDirectory(prefix='mc-ref-sweep-') as temp:
 d=pathlib.Path(temp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');p=pathlib.PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts:raise ValueError('ruta insegura')
    raw=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('checksum inválido')
    target=d/kind/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);cp.append(str(target))
 classpath=os.pathsep.join(cp);subprocess.run([str(jdk/'javac'),'-cp',classpath,'-d',str(d),str(here/'ReferenceSweep.java')],check=True)
 refargs=[arg for r in methods for arg in (r['class'].replace('/','.'),r['getter'])]
 ref=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+classpath,'ReferenceSweep',*refargs],capture_output=True,text=True,check=True).stdout.splitlines()
 if len(ref)!=len(methods):raise RuntimeError('salida JVM incompleta')
 for i,(method,expected) in enumerate(zip(methods,ref)):
  binary=d/str(i)
  cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','reference-demo',str(jar),method['class'],method['getter'],str(binary)]
  subprocess.run(cmd,capture_output=True,text=True,check=True)
  run=subprocess.run([str(binary),'string','Alpha','new','0','get','1','eq','0','2','text','2','string','Alpha','eq','2','3','null','new','4','get','5','eq','4','6'],capture_output=True,text=True,check=True)
  actual=','.join(run.stdout.splitlines())
  if actual!=expected:raise AssertionError((method,actual,expected))
 print(f'OK: {len(methods)} pares reales constructor/getter comparados con Java 25; identidad y null')
