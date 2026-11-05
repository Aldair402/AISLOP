#!/usr/bin/env python3
"""Flags exactos y clase declarante de Member registrados, invocados por interfaz y clase."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'MemberModsProbe.java':'''package net.minecraft.test;import java.lang.reflect.*;public class MemberModsProbe{public static int run(int n){try{Constructor<?> c=Target.class.getDeclaredConstructor();Method a=Target.class.getMethod("plain"),b=Target.class.getMethod("finalMethod"),d=Target.class.getMethod("sync");Member m=n%4==0?c:n%4==1?a:n%4==2?b:d;return m.getModifiers()*100+(m.getDeclaringClass()==Target.class?1:0)+(c.getModifiers()==1?2:0)+(b.getDeclaringClass()==Target.class?4:0);}catch(ReflectiveOperationException e){return -1;}}public static int nil(int n){try{Member m=null;return m.getModifiers();}catch(NullPointerException e){return 20;}}}''',
'Target.java':'''package net.minecraft.test;public class Target{public Target(){}public String plain(){return "a";}public final String finalMethod(){return "b";}public synchronized String sync(){return "c";}}''',
'Driver.java':'''import net.minecraft.test.MemberModsProbe;public class Driver{public static void main(String[]a){for(String n:a){int x=Integer.parseInt(n);System.out.println(MemberModsProbe.run(x));System.out.println(MemberModsProbe.nil(x));}}}'''}
with tempfile.TemporaryDirectory(prefix='mc-member-mods-') as t:
 d=pathlib.Path(t)
 for name,source in sources.items():(d/name).write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/name) for name in sources]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cl='net/minecraft/test/Target';env=dict(os.environ,MC_AOT_REFLECT_CLASSES=cl,MC_AOT_REFLECT_METHODS='|'.join(cl+'#'+n+'#()Ljava/lang/String;' for n in ('plain','finalMethod','sync')))
 for m in ('run','nil'):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MemberModsProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180,env=env)
  if p.returncode:raise RuntimeError((m,p.stderr))
 seq=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout.splitlines();outs=[subprocess.run([str(d/m),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines() for m in ('run','nil')];n=[v for pair in zip(*outs) for v in pair]
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(j)} resultados modificadores de constructor y métodos public/final/synchronized, clase y null')
