#!/usr/bin/env python3
"""Compara constructor y dos getters reales de Minecraft con el objeto generado."""
import hashlib, os, pathlib, random, subprocess, tempfile, zipfile
root=pathlib.Path(__file__).resolve().parent.parent
here=pathlib.Path(__file__).resolve().parent
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
jar=root/'downloads/server-26.3.jar'
native=root/'mc-aot/examples/level-height-object'
with tempfile.TemporaryDirectory(prefix='mc-object-') as tmp:
 d=pathlib.Path(tmp); classpath=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t'); path=pathlib.PurePosixPath(rel)
    if path.is_absolute() or '..' in path.parts: raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum: raise ValueError('checksum inválido')
    out=d/kind/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data);classpath.append(str(out))
 cp=os.pathsep.join(classpath)
 subprocess.run([str(jdk/'javac'),'-cp',cp,'-d',str(d),str(here/'ObjectReference.java')],check=True)
 randomizer=random.Random(2026)
 values=[(-2147483648,2147483647),(0,0),(384,-64),(-1,1),(2147483647,-2147483648)]
 values += [(randomizer.randint(-2147483648,2147483647),randomizer.randint(-2147483648,2147483647)) for _ in range(150)]
 proc=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+cp,'ObjectReference'],input=''.join(f'{a},{b}\n' for a,b in values),text=True,capture_output=True,check=True)
 lines=proc.stdout.splitlines()
 if len(lines)!=len(values):raise RuntimeError(f'La JVM devolvió {len(lines)} líneas, se esperaban {len(values)}')
 for (a,b),expected in zip(values,lines):
  out=subprocess.run([str(native),str(a),str(b),'getHeight','getMinY','getMaxY','getHeight'],text=True,capture_output=True,check=True)
  actual=','.join(out.stdout.splitlines())
  if actual!=expected:raise AssertionError((a,b,actual,expected))
 bad=subprocess.run([str(native),'384','-64','missing'],text=True,capture_output=True)
 if bad.returncode==0:raise AssertionError('método inexistente no se rechazó')
 print(f'OK: {len(values)} objetos, {len(values)*4} llamadas coinciden con Minecraft en Java 25')
