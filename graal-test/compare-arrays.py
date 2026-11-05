#!/usr/bin/env python3
"""Pruebas diferenciales JVM/nativo de arrays primitivos, identidad y errores."""
import hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
fixture='''package net.minecraft.test;
public class ArrayFixture {
 public static int sum(int[] a){int n=0;for(int x:a)n+=x;return n;}
 static int get(int[] a,int i){return a[i];}
 public static int writeInt(int[] a,int i,int x){a[i]=x;return get(a,i)+a.length;}
 public static long writeLong(long[] a,int i,long x){a[i]=x;return a[i]+a.length;}
 public static int writeByte(byte[] a,int i,int x){a[i]=(byte)x;return a[i];}
 public static int writeChar(char[] a,int i,int x){a[i]=(char)x;return a[i];}
 public static int writeShort(short[] a,int i,int x){a[i]=(short)x;return a[i];}
 public static int writeBool(boolean[] a,int i,boolean x){a[i]=x;return a[i]?1:0;}
 public static int defaults(int n){byte[] b=new byte[n];short[] s=new short[n];char[] c=new char[n];boolean[] z=new boolean[n];return n==0?0:b[0]+s[0]+c[0]+(z[0]?1:0);}
 public static int allocate(int n,int x){int[] a=new int[n];if(n>0)a[0]=x;return n>0?a[0]+a.length:a.length;}
 public static long allocateLong(int n,long x){long[] a=new long[n];if(n>0)a[0]=x;return n>0?a[0]+a.length:a.length;}
 public static int alias(int[] a,int x){int[] b=a;if(a==b && a!=null){a[0]=x;return b[0];}return -1;}
 public static int same(int[] a,int[] b){return a==b?1:0;}
 public static int nullref(){int[] a=null;return a==null?7:0;}
}'''
with tempfile.TemporaryDirectory(prefix='mc-array-compare-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 (d/'ArrayFixture.java').write_text(fixture)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ArrayFixture.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 subprocess.run([str(jdk/'javac'),'-cp',os.pathsep.join([str(d),*cp]),'-d',str(d),str(root/'graal-test/ArrayReference.java')],check=True)
 specs={f'opt{t}':(jar,'net/minecraft/Optionull','isNullOrEmpty',f'([{t})Z') for t in 'IJBCSZ'}
 specs.update({'little':(jar,'net/minecraft/server/rcon/PktUtils','intFromByteArray','([BII)I'),'little2':(jar,'net/minecraft/server/rcon/PktUtils','intFromByteArray','([BI)I'),'big':(jar,'net/minecraft/server/rcon/PktUtils','intFromNetworkByteArray','([BII)I'),
 'biome':(jar,'net/minecraft/util/datafix/fixes/ChunkHeightAndBiomeFix','getOldBiome','([II)I')})
 for label,name,desc in [('sum','sum','([I)I'),('wi','writeInt','([III)I'),('wj','writeLong','([JIJ)J'),('wb','writeByte','([BII)I'),('wc','writeChar','([CII)I'),('ws','writeShort','([SII)I'),('wz','writeBool','([ZIZ)I'),('defaults','defaults','(I)I'),('alloc','allocate','(II)I'),('allocJ','allocateLong','(IJ)J'),('alias','alias','([II)I'),('same','same','([I[I)I'),('nullref','nullref','()I')]:specs[label]=(d/'test.jar','net/minecraft/test/ArrayFixture',name,desc)
 for label,(j,c,m,desc) in specs.items():
  cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--',('compile-numeric' if label in ('alloc','nullref') else 'compile'),str(j),c,m,desc,str(d/label)]
  p=subprocess.run(cmd,capture_output=True,text=True)
  if p.returncode:raise RuntimeError((label,p.stderr))
 rng=random.Random(4059);programs=[]
 for label in ('optI','optJ','optB','optC','optS','optZ'):
  for a in ('null','[]','[0]','[1,0,1]'):programs.append((label,a))
 programs += [('same','[5]','@0'),('same','[5]','[5]'),('same','null','@0'),('same','null','null'),('same','[]','[]'),('nullref',)]
 programs += [('sum','null'),('wi','null',0,1),('wi','[]',0,1),('alias','null',17),('alias','[]',17)]
 for i in range(100):
  n=rng.randint(0,9);idx=rng.randint(-2,n+2); ints=[rng.randint(-(1<<31),(1<<31)-1) for _ in range(n)];b=[rng.randint(-128,127) for _ in range(n)];z=[rng.randrange(2) for _ in range(n)];
  char=[rng.randint(0,65535) for _ in range(n)]; shorts=[rng.randint(-32768,32767) for _ in range(n)]; longs=[rng.randint(-(1<<63),(1<<63)-1) for _ in range(n)]
  fmt=lambda x:'['+','.join(map(str,x))+']';x=rng.randint(-(1<<31),(1<<31)-1);y=rng.randint(-(1<<63),(1<<63)-1)
  programs += [('sum',fmt(ints)),('wi',fmt(ints),idx,x),('wj',fmt(longs),idx,y),('wb',fmt(b),idx,x),('wc',fmt(char),idx,x),('ws',fmt(shorts),idx,x),('wz',fmt(z),idx,i%2),('alias',fmt(ints),x),('biome',fmt(ints),idx)]
  programs += [('little',fmt(b),idx,n),('little2',fmt(b),idx),('big',fmt(b),idx,n),('defaults',i%12-2),('alloc',i%12-2,x),('allocJ',i%12-2,y)]
 inp=''.join('|'.join(map(str,row))+'\n' for row in programs)
 jp=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'ArrayReference'],input=inp,capture_output=True,text=True,timeout=90)
 if jp.returncode:raise RuntimeError('Java falló: '+jp.stderr[-5000:])
 ref=jp.stdout.splitlines()
 if len(ref)!=len(programs):raise AssertionError(('Java line count',len(ref),len(programs),ref[:5]))
 counts={}
 for (label,*args),expected in zip(programs,ref):
  native=subprocess.run([str(d/label),*map(str,args)],capture_output=True,text=True,timeout=5)
  if expected.startswith('ERR:'):
   category=expected[4:];counts[category]=counts.get(category,0)+1
   if native.returncode==0 or category not in native.stderr:raise AssertionError((label,args,expected,native.returncode,native.stdout,native.stderr))
  elif native.returncode or native.stdout.strip()!=expected:raise AssertionError((label,args,expected,native.returncode,native.stdout,native.stderr))
 for label,args in [('optI',['[2147483648]']),('optZ',['[2]']),('optB',['[-129]']),('same',['[1]','@1']),('optI',['[1,,2]']),('optI',['1,2'])]:
  p=subprocess.run([str(d/label),*args],capture_output=True,text=True)
  if p.returncode==0:raise AssertionError(('se aceptó entrada inválida',label,args))
 limit=subprocess.run([str(d/'alloc'),'1000001','0'],capture_output=True,text=True)
 if limit.returncode==0 or 'Límite experimental' not in limit.stderr:raise AssertionError('límite de heap')
 print(f'OK: {len(programs)} resultados; 10 métodos reales y 13 sintéticos coinciden con Java 25; errores por categoría {counts}; 6 entradas inválidas y límite rechazados')
