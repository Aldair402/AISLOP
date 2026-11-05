#!/usr/bin/env python3
"""Member: constructor/método reflectivos registrados y null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'MemberProbe.java':'''package net.minecraft.test;import java.lang.reflect.*;public class MemberProbe{public static int run(int n){try{Object a=n%4==0?null:n%4==1?Target.class.getDeclaredConstructor():n%4==2?Target.class.getMethod("value"):"x";boolean b=a instanceof Member;Member m=(Member)a;return (b?1:0)+(m==a?2:0);}catch(ClassCastException e){return 7;}catch(ReflectiveOperationException e){return 8;}}}''',
'Target.java':'''package net.minecraft.test;public class Target{public Target(){}public String value(){return "a";}}''',
'Driver.java':'''import net.minecraft.test.MemberProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(MemberProbe.run(Integer.parseInt(n)));}}'''}
with tempfile.TemporaryDirectory(prefix='mc-member-cast-') as t:
 d=pathlib.Path(t)
 for name,source in sources.items():(d/name).write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),*[str(d/name) for name in sources]],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 env=dict(os.environ,MC_AOT_REFLECT_CLASSES='net/minecraft/test/Target',MC_AOT_REFLECT_METHODS='net/minecraft/test/Target#value#()Ljava/lang/String;');p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MemberProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} resultados Member constructor/método/null/String')
