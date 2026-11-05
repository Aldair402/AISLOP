#!/usr/bin/env python3
"""Compara preparación e inicializador real de BiomeManager con Java 25."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
fields=['CHUNK_CENTER_QUART','ZOOM_BITS','ZOOM','ZOOM_MASK']
with tempfile.TemporaryDirectory(prefix='mc-static-real-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(root/'graal-test/StaticInitReference.java')],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','static-demo',str(jar),'net/minecraft/world/level/biome/BiomeManager',str(d/'native')]
 for field in fields:cmd+=['@'+field,'I']
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(2388);ops=[0,1,2,3]*4+[rng.randrange(4) for _ in range(100)]
 ref=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'StaticInitReference',*map(str,ops)],capture_output=True,text=True,check=True).stdout.splitlines()
 native=subprocess.run([str(d/'native'),*map(str,ops)],capture_output=True,text=True,check=True).stdout.splitlines()
 if ref!=native or ref[:4]!=['2','2','4','3']:raise AssertionError((ref[:10],native[:10]))
 print(f'OK: {len(ops)} lecturas de cuatro campos de BiomeManager; <clinit> y QuartPos.fromBlock coinciden con Java 25')
