#!/usr/bin/env python3
"""Bytecode oficial MR-JAR StackLocator.getCallerClass(int) para prefijos de frames conocidos."""
import hashlib,io,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];project=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import org.apache.logging.log4j.util.StackLocator;
class StackA {static Class<?> ask(int n){return StackLocator.getInstance().getCallerClass(n);}static Class<?> sentinel(int n){Class<?> start=(n&4)!=0?null:(n&1)==0?StackLocator.class:StackA.class;java.util.function.Predicate<Class<?>> p=(n&8)!=0?null:c->{RealStackProbe.calls++;return (n&2)==0||c!=StackA.class;};return StackLocator.getInstance().getCallerClass(start,p);}static Class<?> beyond(){return StackLocator.getInstance().getCallerClass(RealStackProbe.class,c->true);}}
public class RealStackProbe {static int calls;public static int sentinel(int n){calls=0;try{Class<?> c=StackA.sentinel(n);return calls*10+(c==StackA.class?1:c==RealStackProbe.class?2:99);}catch(IllegalArgumentException e){return 100;}}public static int beyond(int n){return StackA.beyond()==null?0:1;}public static int run(int n){try{Class<?> c=StackA.ask(n%3);return c==StackLocator.class?1:c==StackA.class?2:c==RealStackProbe.class?3:99;}catch(IllegalArgumentException e){return 10;}}public static int external(int n){return StackA.ask(50)==null?1:0;}}
'''
driver='''import net.minecraft.test.RealStackProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("sentinel")?RealStackProbe.sentinel(n):RealStackProbe.run(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-log4j-stack-') as t:
 d=pathlib.Path(t)
 with zipfile.ZipFile(project/'downloads/server-26.3.jar') as z:
  entry=next(l.split('\t') for l in z.read('META-INF/libraries.list').decode().splitlines() if 'log4j-api/2.26.0/' in l);api=z.read('META-INF/libraries/'+entry[2]);assert hashlib.sha256(api).hexdigest()==entry[0]
 with zipfile.ZipFile(io.BytesIO(api)) as z:official=z.read('META-INF/versions/9/org/apache/logging/log4j/util/StackLocator.class')
 (d/'api.jar').write_bytes(api);(d/'RealStackProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-cp',str(d/'api.jar'),'-d',str(d/'classes'),str(d/'RealStackProbe.java'),str(d/'Driver.java')],check=True)
 with zipfile.ZipFile(d/'fixture.jar','w') as z:
  for f in (d/'classes/net').rglob('*.class'):z.write(f,f.relative_to(d/'classes').as_posix())
  z.writestr('org/apache/logging/log4j/util/StackLocator.class',official)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RealStackProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
 compile('run');seq=list(range(-45,46));j=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+os.pathsep+str(d/'classes'),'Driver','run',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'run'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 compile('sentinel');j=subprocess.run([str(jdk/'java'),'-cp',str(d/'fixture.jar')+os.pathsep+str(d/'classes'),'Driver','sentinel',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'sentinel'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError(('sentinel',j,n))
 compile('beyond');p=subprocess.run([str(d/'beyond'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'frames externos no modelados' not in p.stderr:raise AssertionError(('sentinel beyond',p.returncode,p.stderr))
 compile('external');p=subprocess.run([str(d/'external'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'frames externos no modelados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)*2} resultados del StackLocator oficial Java 25 para profundidad y sentinel/predicate conocidos, incluidos null; marco externo aborta; SHA-256 {hashlib.sha256(official).hexdigest()}')
