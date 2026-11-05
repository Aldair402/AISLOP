#!/usr/bin/env python3
"""Constructor y onStart oficiales de Util$2, invocados aislados con Tracy sin cargar."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';inner=root.parent/'downloads/server-26.3-inner.jar'
# Stub is used only to compile the caller; it is replaced by the untouched
# official class *before* either Java or AOT sees the fixture.
stub='''package net.minecraft.util;
import java.util.concurrent.*;
class Util$2 extends ForkJoinWorkerThread {final String val$threadName,val$name;Util$2(ForkJoinPool p,String thread,String name){super(p);val$threadName=thread;val$name=name;}protected void onStart(){}}
'''
source='''package net.minecraft.util;
import java.util.concurrent.*;
public class UtilWorkerStartProbe {public static int run(int n){ForkJoinPool p=new ForkJoinPool(1);String thread=n<0?null:"Worker-\\uD83D\\uDE80";String category=(n&1)==0?"Even":"Odd";Util$2 w=new Util$2(p,thread,category);w.onStart();p.shutdown();return n+(w.val$threadName==null?0:w.val$threadName.hashCode())+w.val$name.hashCode();}}
'''
driver='''import net.minecraft.util.UtilWorkerStartProbe;import com.mojang.jtracy.TracyClient;public class Driver{public static void main(String[] a){if(TracyClient.isAvailable())throw new AssertionError("Tracy activo");for(String s:a)System.out.println(UtilWorkerStartProbe.run(Integer.parseInt(s)));}}'''
vals=[0,1,-2,3,100,-101,2147483647,-2147483648,17,-9,42,2]
with tempfile.TemporaryDirectory(prefix='mc-util-worker-onstart-') as temp:
 d=pathlib.Path(temp);(d/'Util$2.java').write_text(stub);(d/'UtilWorkerStartProbe.java').write_text(source);(d/'Driver.java').write_text(driver)
 with zipfile.ZipFile(root.parent/'downloads/server-26.3.jar') as z:
  (d/'jtracy.jar').write_bytes(z.read('META-INF/libraries/com/mojang/jtracy/1.14.38/jtracy-1.14.38.jar'))
 subprocess.run([str(jdk/'javac'),'-cp',str(d/'jtracy.jar'),'-d',str(d),str(d/'Util$2.java'),str(d/'UtilWorkerStartProbe.java'),str(d/'Driver.java')],check=True)
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/util/Util$2.class';official=z.read(name)
 assert hashlib.sha256(official).hexdigest()=='0324db47427384d1dfe3e0e9f61410121af90931d9267f08ec85bc6f164cb205';(d/name).write_bytes(official)
 with zipfile.ZipFile(d/'jtracy.jar') as z:
  name='com/mojang/jtracy/TracyClient.class';b=z.read(name);p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'com'],check=True)
 env=os.environ.copy();env['MC_AOT_RAYON_ASSUME_NO_TRACY']='1'
 native=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'fixture.jar'),'net/minecraft/util/UtilWorkerStartProbe',str(d/'out'),'run','(I)I'],text=True,capture_output=True,env=env,timeout=120)
 if native.returncode:raise RuntimeError(native.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner)+os.pathsep+str(d/'jtracy.jar'),'Driver',*map(str,vals)],text=True,capture_output=True,timeout=30,check=True)
 args=[]
 for n in vals:args.extend([str(n),'--phase'])
 native=subprocess.run([str(d/'out'),*args],text=True,capture_output=True,timeout=30)
 if native.returncode or native.stdout!=java.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 print('OK: 12 resultados con constructor y onStart de Util$2 oficiales, invocados directamente con Tracy desactivado y nombres Unicode/null; no prueba ciclo de vida completo ni logger')
