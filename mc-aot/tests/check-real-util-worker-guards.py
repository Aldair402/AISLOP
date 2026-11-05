#!/usr/bin/env python3
"""Probe de compilación: worker Util$2 oficial con lambda sintética; NO arranca servidor."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
inner=root.parent/'downloads/server-26.3-inner.jar'
source='''package net.minecraft.util;
import java.util.concurrent.*;import java.util.concurrent.atomic.AtomicInteger;
public class RealUtilWorkerProbe {
 public static int run(int n){String group="Probe";AtomicInteger counter=new AtomicInteger(n);ForkJoinPool p=new ForkJoinPool(1,pool->{String name="Worker-"+group+"-"+counter.getAndIncrement();ForkJoinWorkerThread w=new ForkJoinWorkerThread(pool){protected void onStart(){RealUtilWorkerProbe.score(name.hashCode()+group.hashCode());}protected void onTermination(Throwable t){}};w.setName(name);return w;},null,true);p.shutdown();return n;}
 public static void score(int n){}
}
'''
with tempfile.TemporaryDirectory(prefix='mc-real-util-worker-') as temp:
 d=pathlib.Path(temp);(d/'RealUtilWorkerProbe.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RealUtilWorkerProbe.java')],check=True)
 # Rewrite only the fixture's anonymous-class reference to the *official* worker.
 # This artificial caller is not executed by Java and is not Minecraft's Util.
 probe=d/'net/minecraft/util/RealUtilWorkerProbe.class';b=probe.read_bytes()
 old=b'net/minecraft/util/RealUtilWorkerProbe$1';new=b'net/minecraft/util/Util$2'
 a=len(old).to_bytes(2,'big')+old;c=len(new).to_bytes(2,'big')+new
 assert b.count(a)==1;probe.write_bytes(b.replace(a,c))
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/util/Util$2.class';official=z.read(name)
 assert hashlib.sha256(official).hexdigest()=='0324db47427384d1dfe3e0e9f61410121af90931d9267f08ec85bc6f164cb205'
 worker=d/name;worker.write_bytes(official)
 with zipfile.ZipFile(root.parent/'downloads/server-26.3.jar') as z:lib=d/'jtracy.jar';lib.write_bytes(z.read('META-INF/libraries/com/mojang/jtracy/1.14.38/jtracy-1.14.38.jar'))
 with zipfile.ZipFile(lib) as z:
  name='com/mojang/jtracy/TracyClient.class';p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
 def jar(name):subprocess.run([str(jdk/'jar'),'cf',str(d/name),'-C',str(d),'net','-C',str(d),'com'],check=True)
 jar('fixture.jar')
 base=os.environ.copy();base.pop('MC_AOT_RAYON_ASSUME_NO_TRACY',None)
 def compile(name,allow):
  env=base.copy()
  if allow:env['MC_AOT_RAYON_ASSUME_NO_TRACY']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/name),'net/minecraft/util/RealUtilWorkerProbe',str(d/'out'),'run','(I)I'],text=True,capture_output=True,env=env,timeout=120)
 p=compile('fixture.jar',False)
 if p.returncode==0 or 'MC_AOT_RAYON_ASSUME_NO_TRACY=1' not in p.stderr:raise AssertionError(('guardia Tracy',p.returncode,p.stderr))
 p=compile('fixture.jar',True)
 if p.returncode==0 or 'campo externo no soportado: net/minecraft/util/Util.LOGGER' not in p.stderr:raise AssertionError(('logger real pendiente',p.returncode,p.stderr))
 modified=official.replace(b'Util.java',b'Xtil.java');assert modified!=official;worker.write_bytes(modified);jar('modified.jar')
 p=compile('modified.jar',True)
 if p.returncode==0 or 'Util$2: versión de clase no verificada' not in p.stderr:raise AssertionError(('guardia hash worker',p.returncode,p.stderr))
 print('OK: Util$2 oficial y constructor registrados por patrón con llamador artificial; rechazos Tracy sin opt-in, LOGGER no implementado y clase modificada; no se ejecutó worker ni se produjo binario')
