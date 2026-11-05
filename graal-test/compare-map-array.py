#!/usr/bin/env python3
"""Compara MapItem tras bootstrap JVM de registros, sin iniciar el servidor."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
with tempfile.TemporaryDirectory(prefix='mc-map-array-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-cp',os.pathsep.join(cp),'-d',str(d),str(root/'graal-test/MapArrayReference.java')],capture_output=True,text=True,check=True)
 subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(jar),'net/minecraft/world/item/MapItem','isBiomeWatery','([ZII)Z',str(d/'native')],capture_output=True,text=True,check=True)
 rng=random.Random(914);rows=[('null',0,0),('[]',0,0),('[1]',0,0)]
 for i in range(80):
  n=rng.choice([1,4,128,256,512]);arr='['+','.join(str(rng.randrange(2)) for _ in range(n))+']';x=rng.choice([-129,-1,0,1,3,127,128,2147483647]);y=rng.choice([-1,0,1,2,2147483647]);rows.append((arr,x,y))
 inp=''.join('|'.join(map(str,row))+'\n' for row in rows)
 p=subprocess.run([str(jdk/'java'),'-Xmx768m','-cp',os.pathsep.join([str(d),*cp]),'MapArrayReference'],input=inp,capture_output=True,text=True,timeout=120,cwd=d)
 if p.returncode:raise RuntimeError('Bootstrap JVM falló: '+p.stderr[-4000:]+p.stdout[-4000:])
 ref=[x.split('\t',1)[1] for x in p.stderr.splitlines() if x.startswith('MCRESULT\t')]
 if len(ref)!=len(rows):raise AssertionError(('salida incompleta',len(ref),len(rows),p.stderr[-2000:]))
 for args,want in zip(rows,ref):
  n=subprocess.run([str(d/'native'),*map(str,args)],capture_output=True,text=True,timeout=5)
  if want.startswith('ERROR:'):
   if n.returncode==0 or want[6:] not in n.stderr:raise AssertionError((args,want,n.returncode,n.stderr))
  elif n.returncode or n.stdout.strip()!=want:raise AssertionError((args,want,n.returncode,n.stdout,n.stderr))
 print(f'OK: {len(rows)} resultados de MapItem.isBiomeWatery coinciden con Java 25 después del bootstrap de registros; errores por categoría; no se inició el servidor')
