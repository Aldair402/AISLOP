#!/usr/bin/env python3
"""AccessibleObject: override desactivado, setAccessible(true) rechazado."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'AccessProbe.java':'''package net.minecraft.test;import java.lang.reflect.*;public class AccessProbe{public static int run(int n){try{AccessibleObject a=(n&1)==0?Target.class.getDeclaredConstructor():Target.class.getMethod("value");boolean initial=a.isAccessible();a.setAccessible(false);return (initial?10:0)+(a.isAccessible()?100:1);}catch(ReflectiveOperationException e){return 8;}}public static int unsupported(int n){try{Constructor<?> a=Target.class.getDeclaredConstructor();a.setAccessible(true);return a.isAccessible()?1:0;}catch(ReflectiveOperationException e){return 8;}}public static int nil(int n){try{AccessibleObject a=null;return a.isAccessible()?1:0;}catch(NullPointerException e){return 3;}}}''',
'Target.java':'''package net.minecraft.test;public class Target{public Target(){}public String value(){return "a";}}''',
'Driver.java':'''import net.minecraft.test.AccessProbe;public class Driver{public static void main(String[]a){for(String n:a){int x=Integer.parseInt(n);System.out.println(AccessProbe.run(x));System.out.println(AccessProbe.nil(x));}}}'''}
with tempfile.TemporaryDirectory(prefix='mc-accessible-') as t:
 d=pathlib.Path(t)
 for name,source in sources.items():(d/name).write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/name) for name in sources]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cl='net/minecraft/test/Target';env=dict(os.environ,MC_AOT_REFLECT_CLASSES=cl,MC_AOT_REFLECT_METHODS=cl+'#value#()Ljava/lang/String;')
 for m in ('run','nil','unsupported'):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/AccessProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180,env=env)
  if p.returncode:raise RuntimeError((m,p.stderr))
 seq=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout.splitlines();outs=[subprocess.run([str(d/m),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines() for m in ('run','nil')];n=[v for pair in zip(*outs) for v in pair]
 if j!=n:raise AssertionError((j,n))
 p=subprocess.run([str(d/'unsupported'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'AccessibleObject.setAccessible(true): acceso no verificado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(j)} resultados isAccessible/setAccessible(false)/null; setAccessible(true) aborta')
