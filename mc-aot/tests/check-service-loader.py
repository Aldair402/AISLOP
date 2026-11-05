#!/usr/bin/env python3
"""Descubrimiento real META-INF/services de bundles y proveedores registrados."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'Svc.java':'''package net.minecraft.test;public interface Svc {}''',
'FailSvc.java':'''package net.minecraft.test;public interface FailSvc {}''',
'WrongSvc.java':'''package net.minecraft.test;public interface WrongSvc {}''',
'NoCtorSvc.java':'''package net.minecraft.test;public interface NoCtorSvc {}''',
'First.java':'''package net.minecraft.test;public class First implements Svc {public First(){ServiceDemo.count++;}}''',
'Second.java':'''package net.minecraft.test;public class Second implements Svc,FailSvc {public Second(){ServiceDemo.count+=10;}}''',
'Broken.java':'''package net.minecraft.test;public class Broken implements FailSvc {public Broken(){throw ServiceDemo.marker;}}''',
'Wrong.java':'''package net.minecraft.test;public class Wrong {public Wrong(){}}''',
'NoCtor.java':'''package net.minecraft.test;public class NoCtor implements NoCtorSvc {private NoCtor(){}}''',
'ServiceDemo.java':'''package net.minecraft.test;
import java.util.*;
public class ServiceDemo {
 public static int count=1;public static IllegalArgumentException marker=new IllegalArgumentException();
 static ServiceLoader<Svc> service=ServiceLoader.load(Svc.class,ServiceDemo.class.getClassLoader());
 static Iterator<Svc> a,b;static Object first,second;static Iterator<FailSvc> failure;
 public static int run(int n){try{switch(n){
 case 0:a=((Iterable<Svc>)service).iterator();return a.hasNext()?count*100+1:-1;
 case 1:first=a.next();return (first instanceof First?1:0)+count*100;
 case 2:b=((Iterable<Svc>)service).iterator();return b.next()==first?2:0;
 case 3:second=a.next();return (second instanceof Second?3:0)+count*100;
 case 4:return b.next()==second?4:0;
 case 5:return !a.hasNext()&&!b.hasNext()?5:0;
 case 6:a.next();return -1;
 case 7:failure=ServiceLoader.load(FailSvc.class,ServiceDemo.class.getClassLoader()).iterator();return failure.hasNext()?7:0;
 case 8:failure.next();return -1;
 case 9:return failure.hasNext()&&failure.next() instanceof Second?count:0;
 case 10:return !failure.hasNext()?10:0;
 case 11:Iterator<WrongSvc> wrong=ServiceLoader.load(WrongSvc.class,ServiceDemo.class.getClassLoader()).iterator();if(!wrong.hasNext())return -2;wrong.next();return -1;
 case 12:Iterator<NoCtorSvc> missing=ServiceLoader.load(NoCtorSvc.class,ServiceDemo.class.getClassLoader()).iterator();if(!missing.hasNext())return -2;missing.next();return -1;
 default:return count;
 }}catch(NoSuchElementException e){return 106;}catch(ServiceConfigurationError e){
 if(n==8)return e.getCause()==marker&&e.getMessage().equals("net.minecraft.test.FailSvc: Provider net.minecraft.test.Broken could not be instantiated")?108:-108;
 if(n==11)return e.getCause()==null&&e.getMessage().equals("net.minecraft.test.WrongSvc: net.minecraft.test.Wrong not a subtype")?111:-111;
 if(n==12)return e.getCause()!=null&&e.getMessage().equals("net.minecraft.test.NoCtorSvc: net.minecraft.test.NoCtor Unable to get public no-arg constructor")?111:-112;
 return -113;}}
}''',
'ServiceDriver.java':'''import net.minecraft.test.ServiceDemo;public class ServiceDriver{public static void main(String[] a){for(String s:a)System.out.println(ServiceDemo.run(Integer.parseInt(s)));}}'''}
with tempfile.TemporaryDirectory(prefix='mc-service-') as t:
 d=pathlib.Path(t)
 for name,text in sources.items():(d/name).write_text(text)
 subprocess.run([str(jdk/'javac'),'-d',str(d/'classes'),*[str(d/x) for x in sources]],check=True)
 prefix='META-INF/services/net.minecraft.test.'
 first={prefix+'Svc':b' # comment\r\n net.minecraft.test.First # comment\nnet.minecraft.test.First\n',prefix+'FailSvc':b'net.minecraft.test.Broken\n',prefix+'WrongSvc':b'net.minecraft.test.Wrong\n',prefix+'NoCtorSvc':b'net.minecraft.test.NoCtor\n'}
 second={prefix+'Svc':b'net.minecraft.test.First\nnet.minecraft.test.Second\n',prefix+'FailSvc':b'net.minecraft.test.Second\n'}
 def makejar(path,resources,include_classes):
  with zipfile.ZipFile(path,'w') as z:
   if include_classes:
    for f in (d/'classes').rglob('*.class'):z.write(f,str(f.relative_to(d/'classes')))
   for name,data in resources.items():z.writestr(name,data)
 makejar(d/'v.jar',first,True);makejar(d/'lib.jar',second,False)
 def bundle(path):
  with zipfile.ZipFile(path,'w') as z:
   for kind,jar,n in [('versions',d/'v.jar','v.jar'),('libraries',d/'lib.jar','lib.jar')]:
    b=jar.read_bytes();z.writestr(f'META-INF/{kind}.list',f'{hashlib.sha256(b).hexdigest()}\tid\t{n}\n');z.writestr(f'META-INF/{kind}/{n}',b)
 bundle(d/'bundle.jar');env=dict(os.environ,MC_AOT_REFLECT_CLASSES=':'.join('net/minecraft/test/'+n for n in ('First','Second','Broken','Wrong','NoCtor')))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'bundle.jar'),'net/minecraft/test/ServiceDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(map(str,range(13)));java=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d/'v.jar'),str(d/'lib.jar')]),'ServiceDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 # Sin registro no se debe fingir que el servicio está vacío.
 env.pop('MC_AOT_REFLECT_CLASSES');p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'bundle.jar'),'net/minecraft/test/ServiceDemo',str(d/'guarded'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'guarded'),'0','0','0','1'],capture_output=True,text=True)
 if p.returncode!=2 or 'proveedor no registrado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 13 operaciones Java ServiceLoader y despacho Iterable.iterator: recursos reales en orden, comentarios, duplicados, caché, instanciación, causa y configuración inválida; proveedor no registrado aborta')
