#!/usr/bin/env python3
"""Compara primitivas estrechas en argumentos y llamadas estáticas con Java 25."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
fixture='''package net.minecraft.test;
public class SmallFixture {
 public static int identity(boolean z,byte b,char c,short s) {return (z?1:0)+b+c+s;}
 public static int nested(boolean z,byte b,char c,short s) {return identity(z,b,c,s)*3;}
}'''
with tempfile.TemporaryDirectory(prefix='mc-small-args-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 (d/'SmallFixture.java').write_text(fixture)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SmallFixture.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 subprocess.run([str(jdk/'javac'),'-cp',str(d),'-d',str(d),str(root/'graal-test/SmallArgumentReference.java')],check=True)
 specs={'flags':(jar,'net/minecraft/commands/synchronization/ArgumentUtils','createNumberFlags','(ZZ)I'),
        'min':(jar,'net/minecraft/commands/synchronization/ArgumentUtils','numberHasMin','(B)Z'),
        'x':(jar,'net/minecraft/core/SectionPos','sectionRelativeX','(S)I'),
        'continuation':(jar,'net/minecraft/network/VarInt','hasContinuationBit','(B)Z'),
        'path':(jar,'net/minecraft/resources/Identifier','validPathChar','(C)Z'),
        'nested':(d/'test.jar','net/minecraft/test/SmallFixture','nested','(ZBCS)I')}
 for label,(j,c,m,desc) in specs.items():
  subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(j),c,m,desc,str(d/label)],capture_output=True,text=True,check=True)
 rng=random.Random(125);programs=[]
 programs += [('flags',a,b) for a in (0,1) for b in (0,1)]
 for x in range(-128,128):programs += [('min',x),('continuation',x)]
 programs += [('x',x) for x in [-32768,-1,0,1,32767]+[rng.randint(-32768,32767) for _ in range(75)]]
 programs += [('path',x) for x in list(range(128))+[0xd800,0xdfff,0xffff]+[rng.randint(0,65535) for _ in range(30)]]
 programs += [('nested',rng.randrange(2),rng.randint(-128,127),rng.randint(0,65535),rng.randint(-32768,32767)) for _ in range(70)]
 inp=''.join(','.join(map(str,row))+'\n' for row in programs)
 ref=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'SmallArgumentReference'],input=inp,capture_output=True,text=True,check=True).stdout.splitlines()
 assert len(ref)==len(programs)
 for (label,*args),expected in zip(programs,ref):
  got=subprocess.run([str(d/label),*map(str,args)],capture_output=True,text=True,check=True).stdout.strip()
  if got!=expected:raise AssertionError((label,args,got,expected))
 for label,args in [('flags',[2,0]),('flags',[-1,0]),('min',[128]),('continuation',[-129]),('x',[32768]),('x',[-32769]),('path',[-1]),('path',[65536])]:
  got=subprocess.run([str(d/label),*map(str,args)],capture_output=True,text=True)
  if got.returncode==0 or 'fuera del rango Java' not in got.stderr:raise AssertionError((label,args,got))
 print(f'OK: {len(programs)} resultados; 5 métodos reales y llamada sintética con Z/B/C/S coinciden con Java 25; 8 límites rechazados')
