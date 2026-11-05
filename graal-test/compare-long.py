#!/usr/bin/env python3
"""Diferencial long con coordenadas reales de Minecraft y clases artificiales."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
fixture='''package net.minecraft.test;
public class LongFixture {
 public static int exact(long x){return Math.toIntExact(x);}
 public static long pre(long x){return ++x;}
 public static long floorl(long a,long b){return Math.floorDiv(a,b);}
 public static long modl(long a,long b){return Math.floorMod(a,b);}
 public static int floori(int a,int b){return Math.floorDiv(a,b);}
 public static int modi(int a,int b){return Math.floorMod(a,b);}
 public static long arith(long a,long b){return ((a*31L+b) ^ (a-b)) + ~b;}
 public static long div(long a,long b){return a/b;}
 public static long rem(long a,long b){return a%b;}
 public static long shl(long a,int b){return a<<b;}
 public static long shr(long a,int b){return a>>b;}
 public static long ushr(long a,int b){return a>>>b;}
 public static int cmp(long a,long b){return a<b?-1:a==b?0:1;}
 public static long mix(int a,long b,int c){return ((long)a<<c) ^ b;}
 public static long loop(long a,int n){for(int i=0;i<n;i++)a=a*3+1;return a;}
 public static long choose(long a,int n){switch(n){case 1:return a+1;case 2:return a-1;case 3:return a*2;case 4:return -a;default:return a;}}
 public static long twice(long a){return a++ + a;}
}'''
with tempfile.TemporaryDirectory(prefix='mc-long-compare-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 (d/'LongFixture.java').write_text(fixture)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LongFixture.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 subprocess.run([str(jdk/'javac'),'-cp',os.pathsep.join([str(d),*cp]),'-d',str(d),str(root/'graal-test/LongReference.java')],check=True)
 specs={
  'wrap':(jar,'net/minecraft/server/commands/TimeCommand','wrapTime','(J)I'),
  'distance':(jar,'net/minecraft/server/level/ChunkTrackingView','isWithinDistance','(IIIIIZ)Z'),
  'bounds':(jar,'net/minecraft/util/PngInfo','validateBounds','(IIBB)Z'),
  'sx':(jar,'net/minecraft/core/SectionPos','x','(J)I'), 'sy':(jar,'net/minecraft/core/SectionPos','y','(J)I'), 'sz':(jar,'net/minecraft/core/SectionPos','z','(J)I'),
  'sectionpack':(jar,'net/minecraft/core/SectionPos','asLong','(III)J'), 'offset':(jar,'net/minecraft/core/SectionPos','offset','(JIII)J'),
  'chunkpack':(jar,'net/minecraft/world/level/ChunkPos','pack','(II)J'), 'cx':(jar,'net/minecraft/world/level/ChunkPos','getX','(J)I'),
  'cz':(jar,'net/minecraft/world/level/ChunkPos','getZ','(J)I'), 'sectionchunk':(jar,'net/minecraft/world/level/ChunkPos','fromSectionNode','(J)J'),
 }
 for name,desc in [('exact','(J)I'),('pre','(J)J'),('floorl','(JJ)J'),('modl','(JJ)J'),('floori','(II)I'),('modi','(II)I'),('arith','(JJ)J'),('div','(JJ)J'),('rem','(JJ)J'),('shl','(JI)J'),('shr','(JI)J'),('ushr','(JI)J'),('cmp','(JJ)I'),('mix','(IJI)J'),('loop','(JI)J'),('choose','(JI)J'),('twice','(J)J')]:specs[name]=(d/'test.jar','net/minecraft/test/LongFixture',name,desc)
 for label,(j,c,m,desc) in specs.items():
  subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--',('compile-numeric' if label in ('floori','modi') else 'compile'),str(j),c,m,desc,str(d/label)],capture_output=True,text=True,check=True)
 rng=random.Random(2673);i_min=-(1<<31);i_max=(1<<31)-1;l_min=-(1<<63);l_max=(1<<63)-1
 longs=[l_min,l_min+1,-4294967296,-2147483649,-1,0,1,2147483647,4294967295,l_max]+[rng.randint(l_min,l_max) for _ in range(80)]
 ints=[i_min,-1025,-65,-64,-63,-33,-32,-1,0,1,4,31,32,63,64,65,1024,i_max]+[rng.randint(i_min,i_max) for _ in range(40)]
 programs=[]
 for n,x in enumerate(longs):
  y=longs[(n*19+7)%len(longs)]; shift=ints[(n*13+3)%len(ints)]
  for label in ('sx','sy','sz','cx','cz','sectionchunk','twice','wrap','pre','exact'):programs.append((label,x))
  for label in ('arith','div','rem','cmp','floorl','modl'):programs.append((label,x,y))
  for label in ('shl','shr','ushr'):programs.append((label,x,shift))
  programs += [('mix',ints[n%len(ints)],x,shift),('loop',x,n%9),('choose',x,(n%8)-1),('offset',x,ints[n%len(ints)],ints[(n+1)%len(ints)],ints[(n+2)%len(ints)])]
 for n in range(90):
  a=ints[n%len(ints)];b=ints[(n*7+2)%len(ints)];c=ints[(n*11+3)%len(ints)]
  programs += [('sectionpack',a,b,c),('chunkpack',a,b),('floori',a,b),('modi',a,b),('distance',a,b,c,ints[(n+3)%len(ints)],ints[(n+4)%len(ints)],n%2),('bounds',a,b,16 if n%2 else -1,(n%256)-128)]
 programs += [('div',l_min,-1),('rem',l_min,-1),('div',1,0),('rem',1,0),('floorl',l_min,-1),('modl',l_min,-1),('floorl',3,0),('modl',3,0),('floori',i_min,-1),('modi',i_min,-1),('floori',3,0),('modi',3,0)]
 inp=''.join(','.join(map(str,row))+'\n' for row in programs)
 ref=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'LongReference'],input=inp,capture_output=True,text=True,check=True).stdout.splitlines()
 assert len(ref)==len(programs),(len(ref),len(programs))
 for (label,*args),expected in zip(programs,ref):
  p=subprocess.run([str(d/label),*map(str,args)],capture_output=True,text=True)
  if expected=='ERR_ARITHMETIC':
   if p.returncode==0 or 'ArithmeticException' not in p.stderr:raise AssertionError((label,args,p.returncode,p.stdout,p.stderr,expected))
  elif p.returncode or p.stdout.strip()!=expected:raise AssertionError((label,args,p.returncode,p.stdout,p.stderr,expected))
 for label,args in [('sx',[str(1<<63)]),('mix',[str(1<<31),'0','1'])]:
  p=subprocess.run([str(d/label),*args],capture_output=True,text=True)
  if p.returncode==0:raise AssertionError(('se aceptó entrada fuera de rango',label,args))
 print(f'OK: {len(programs)} resultados: 12 métodos reales y 17 sintéticos coinciden con Java 25; errores aritméticos por categoría')
