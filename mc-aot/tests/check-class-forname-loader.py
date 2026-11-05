#!/usr/bin/env python3
"""Class.forName(name,initialize,loader) solo clases proyecto precompiladas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'ForNameProbe.java':'''package net.minecraft.test;public class ForNameProbe{public static int count;public static int run(int n){try{Class<?> literal=Target.class;ClassLoader l=ForNameProbe.class.getClassLoader();String name=n==0?null:"net.minecraft.test.Target";Class<?> a=Class.forName(name,n%2==0,l);return (a==literal?100:0)+count;}catch(NullPointerException e){return 200+count;}catch(ClassNotFoundException e){return -1;}}
 public static int cast(int n){try{Object x=n%3==0?null:n%3==1?Target.class:"wrong";Class<?> c=(Class<?>)x;return (x instanceof Class?1:0)+(c==x?2:0);}catch(ClassCastException e){return 9;}}
 public static int unknown(int n)throws Exception{return Class.forName("net.minecraft.test.Unknown",false,ForNameProbe.class.getClassLoader())==null?1:0;}
 public static int bootstrap(int n)throws Exception{return Class.forName("java.lang.String",true,null)==null?1:0;}
}''',
'Target.java':'''package net.minecraft.test;public class Target{static{ForNameProbe.count++;}}''',
'ForNameDriver.java':'''import net.minecraft.test.ForNameProbe;public class ForNameDriver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("cast")?ForNameProbe.cast(n):ForNameProbe.run(n));}}}'''}
with tempfile.TemporaryDirectory(prefix='mc-forname-loader-') as tmp:
 d=pathlib.Path(tmp)
 for n,t in sources.items():(d/n).write_text(t)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/n) for n in sources]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method,enabled=True):
  env=os.environ.copy();env.pop('MC_AOT_STANDARD_SYSTEM_LOADER',None)
  if enabled:env['MC_AOT_STANDARD_SYSTEM_LOADER']='1'
  return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ForNameProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,env=env,timeout=180)
 p=compile('run',False)
 if p.returncode==0 or 'MC_AOT_STANDARD_SYSTEM_LOADER=1' not in p.stderr:raise AssertionError(('opt-in',p.stderr))
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[0,1,1,2,1,2,0,2]*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ForNameDriver','run',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('cast')
 if p.returncode:raise RuntimeError(p.stderr)
 castvals=list(range(81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ForNameDriver','cast',*map(str,castvals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in castvals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError(('cast',java.stdout,native.stdout,native.stderr))
 for method,want in [('unknown','clase no precompilada o desconocida'),('bootstrap','loader bootstrap fuera del perfil')]:
  p=compile(method)
  if p.returncode:raise RuntimeError(p.stderr)
  n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
  if n.returncode==0 or want not in n.stderr:raise AssertionError((method,n.stderr))
 print(f'OK: {len(vals)+len(castvals)} resultados Class.forName con loader, inicialización y casts Class; guardas opt-in, no precompilada y bootstrap')
