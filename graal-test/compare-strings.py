#!/usr/bin/env python3
"""Diferencial de cuatro métodos reales y de intrínsecas String frente a Java 25."""
import base64,hashlib,os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3.jar'
fixture=r'''package net.minecraft.test;
public class StringFixture {
 public static int length(String a){return a.length();}
 public static int character(String a,int i){return a.charAt(i);}
 public static boolean eq(String a,String b){return a.equals(b);}
 public static boolean starts(String a,String b){return a.startsWith(b);}
 public static boolean ends(String a,String b){return a.endsWith(b);}
 public static int indexC(String a,int c,int i){return a.indexOf(c,i);}
 public static int indexS(String a,String b,int i){return a.indexOf(b,i);}
 public static String echo(String a){return a;}
 public static boolean intern(){return literal()=="same";}
 private static String literal(){return "same";}
 public static int surrogate(){return "\uD800".charAt(0);}
 public static int lenArray(String[] a){return a.length;}
 public static int itemLen(String[] a,int i){return a[i]==null?-1:a[i].length();}
 public static int arrayAlias(String[] a,String[] b){a[0]="hi";return b[0].length();}
}'''
driver=r'''import java.io.*;import java.nio.charset.StandardCharsets;import java.util.Base64;
public class StringReference {
 static String s(String x){return x.equals("n")?null:new String(Base64.getDecoder().decode(x.substring(1)),StandardCharsets.UTF_8);}
 public static void main(String[] a)throws Exception {var output=System.err;net.minecraft.SharedConstants.tryDetectVersion();net.minecraft.server.Bootstrap.bootStrap();var in=new BufferedReader(new InputStreamReader(System.in));String line;
  while((line=in.readLine())!=null){String[] p=line.split(" ",-1);String op=p[0],x=s(p[1]);Object result;
   try {result=switch(op){
    case "path"->net.minecraft.resources.Identifier.isValidPath(x);
    case "namespace"->net.minecraft.resources.Identifier.isValidNamespace(x);
    case "first","last"->{var m=Class.forName("net.minecraft.world.item.crafting.ShapedRecipePattern").getDeclaredMethod(op.equals("first")?"firstNonEmpty":"lastNonEmpty",String.class);m.setAccessible(true);yield m.invoke(null,x);}
    case "length"->net.minecraft.test.StringFixture.length(x);
    case "character"->net.minecraft.test.StringFixture.character(x,Integer.parseInt(p[2]));
    case "eq"->net.minecraft.test.StringFixture.eq(x,s(p[2]));
    case "starts"->net.minecraft.test.StringFixture.starts(x,s(p[2]));
    case "ends"->net.minecraft.test.StringFixture.ends(x,s(p[2]));
    case "indexC"->net.minecraft.test.StringFixture.indexC(x,Integer.parseInt(p[2]),Integer.parseInt(p[3]));
    case "indexS"->net.minecraft.test.StringFixture.indexS(x,s(p[2]),Integer.parseInt(p[3]));
    case "echo"->net.minecraft.test.StringFixture.echo(x);
    case "intern"->net.minecraft.test.StringFixture.intern();
    case "surrogate"->net.minecraft.test.StringFixture.surrogate();
    default->throw new IllegalArgumentException();};
    if(result instanceof Boolean)output.println("MCRESULT\t"+((Boolean)result?1:0));else output.println("MCRESULT\t"+result);
   }catch(Throwable e){output.println("MCRESULT\tEX:"+(e instanceof java.lang.reflect.InvocationTargetException?e.getCause():e).getClass().getSimpleName());}
  }
 }
}'''
with tempfile.TemporaryDirectory(prefix='mc-strings-') as tmp:
 d=pathlib.Path(tmp);cp=[]
 with zipfile.ZipFile(jar) as z:
  for kind in ('libraries','versions'):
   for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
    checksum,_,rel=line.split('\t');safe=pathlib.PurePosixPath(rel)
    if safe.is_absolute() or '..' in safe.parts:raise ValueError('ruta insegura')
    data=z.read(f'META-INF/{kind}/{rel}')
    if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum incorrecto')
    target=d/kind/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);cp.append(str(target))
 (d/'StringFixture.java').write_text(fixture,encoding='utf8');(d/'StringReference.java').write_text(driver,encoding='utf8')
 subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-cp',os.pathsep.join(cp),'-d',str(d),str(d/'StringFixture.java'),str(d/'StringReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 specs={}
 for n,m in [('path','isValidPath'),('namespace','isValidNamespace')]:specs[n]=(jar,'net/minecraft/resources/Identifier',m,'(Ljava/lang/String;)Z')
 for n,m in [('first','firstNonEmpty'),('last','lastNonEmpty')]:specs[n]=(jar,'net/minecraft/world/item/crafting/ShapedRecipePattern',m,'(Ljava/lang/String;)I')
 for n,desc in [('length','(Ljava/lang/String;)I'),('character','(Ljava/lang/String;I)I'),('eq','(Ljava/lang/String;Ljava/lang/String;)Z'),('starts','(Ljava/lang/String;Ljava/lang/String;)Z'),('ends','(Ljava/lang/String;Ljava/lang/String;)Z'),('indexC','(Ljava/lang/String;II)I'),('indexS','(Ljava/lang/String;Ljava/lang/String;I)I'),('echo','(Ljava/lang/String;)Ljava/lang/String;'),('intern','()Z'),('surrogate','()I'),('lenArray','([Ljava/lang/String;)I'),('itemLen','([Ljava/lang/String;I)I'),('arrayAlias','([Ljava/lang/String;[Ljava/lang/String;)I')]:specs[n]=(d/'test.jar','net/minecraft/test/StringFixture',n,desc)
 for label,(j,c,m,desc) in specs.items():
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(j),c,m,desc,str(d/label)],capture_output=True,text=True)
  if p.returncode:raise RuntimeError((label,p.stderr))
 def enc(s):return 'n' if s is None else 'x'+base64.b64encode(s.encode()).decode()
 rng=random.Random(841);strings=['','abc','..','minecraft','foo/bar','Upper','a b','á村🚀','🚀','🚀 🚀',' abc ','    ','null',None]+[''.join(rng.choices('abc/ .012_-🚀',k=rng.randrange(18))) for _ in range(28)]
 cases=[]
 for op in ['path','namespace','first','last','length','echo']:
  cases += [(op,[s]) for s in strings]
 for s in strings:
  if s is not None:
   units=len(s.encode('utf-16-le'))//2
   cases += [('character',[s,i]) for i in [-1,0,units-1,units,units+1]]
  for b in [None,'','a','🚀','..',s]:
   for op in ('eq','starts','ends'):cases.append((op,[s,b]))
   for i in [-3,0,1,999]:cases.append(('indexS',[s,b,i]))
  for c in [-1,0,32,97,0xd800,0xde80,0x1f680,0x110000]:
   for i in [-1,0,2,999]:cases.append(('indexC',[s,c,i]))
 cases += [('intern',[]),('surrogate',[])]
 def line(op,args):return ' '.join([op]+[enc(args[0]) if args else enc('')]+[enc(x) if isinstance(x,str) or x is None else str(x) for x in args[1:]])
 inp=''.join(line(op,args)+'\n' for op,args in cases)
 result=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),*cp]),'StringReference'],input=inp,capture_output=True,text=True,check=True)
 ref=[line.split('\t',1)[1] for line in result.stderr.splitlines() if line.startswith('MCRESULT\t')]
 if len(ref)!=len(cases):raise AssertionError(('lines',len(ref),len(cases),ref[:10]))
 for (op,args),expected in zip(cases,ref):
  native_args=[('null' if x is None else 's:'+x) if isinstance(x,str) or x is None else str(x) for x in args]
  got=subprocess.run([str(d/op),*native_args],capture_output=True,text=True)
  if expected.startswith('EX:'):
   if got.returncode==0 or expected[3:] not in got.stderr:raise AssertionError((op,args,expected,got.stdout,got.stderr))
  elif got.returncode or got.stdout.rstrip('\n')!=expected:raise AssertionError((op,args,expected,got.stdout,got.stderr))
 # Array CLI and aliases; null, Unicode, bounds and malformed encodings.
 for op,args,want in [('lenArray',['sarr:[]'],'0'),('lenArray',['sarr:[x,n,xf09f9a80]'],'3'),('itemLen',['sarr:[x,n,xf09f9a80]','2'],'2'),('itemLen',['sarr:[x,n]','1'],'-1'),('arrayAlias',['sarr:[x61]','@0'],'2')]:
  p=subprocess.run([str(d/op),*args],capture_output=True,text=True,check=True)
  if p.stdout.strip()!=want:raise AssertionError((op,args,p.stdout))
 for op,args,err in [('itemLen',['sarr:[]','0'],'ArrayIndexOutOfBoundsException'),('lenArray',['null'],'NullPointerException'),('lenArray',['sarr:[xz]'],'String[] hex inválido'),('arrayAlias',['sarr:[]','@3'],'Alias de array fuera de rango')]:
  p=subprocess.run([str(d/op),*args],capture_output=True,text=True)
  if p.returncode==0 or err not in p.stderr:raise AssertionError((op,args,p.stderr))
 print(f'OK: {len(cases)} casos de 4 métodos reales y 10 sintéticos frente a Java 25; 5 casos String[] y 4 rechazos verificados')
