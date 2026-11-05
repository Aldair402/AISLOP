#!/usr/bin/env python3
"""Métodos reflectivos públicos directos registrados: comparativa y guardas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.lang.reflect.*;public class ReflectMethodDemo {
 public static class Arg {} public static class Target {public String echo(Arg a){return a==null?"null":"ok";}public void fail(Arg a){throw new IllegalArgumentException();}public String zero(){return "zero";}}
 public static int run(int n){try{Target t=new Target();Method m=Target.class.getMethod(n==7?"zero":n==6?"fail":"echo",n==7?new Class[0]:new Class[]{Arg.class});switch(n){case 0:return ((String)m.invoke(t,new Arg())).equals("ok")?1:0;case 1:return ((String)m.invoke(t,new Object[]{null})).equals("null")?2:0;case 2:m.invoke(null,new Object[0]);return 0;case 3:m.invoke(new Object(),new Object[0]);return 0;case 4:m.invoke(t,new Object());return 0;case 5:m.invoke(t,new Object[0]);return 0;case 6:m.invoke(t,new Arg());return 0;case 7:return ((String)m.invoke(t)).equals("zero")?7:0;case 8:Target.class.getMethod("other",Arg.class);return 0;default:return 99;}}catch(NullPointerException e){return 102;}catch(IllegalArgumentException e){return 103;}catch(InvocationTargetException e){return e.getCause().getClass().getName().equals("java.lang.IllegalArgumentException")?106:0;}catch(ReflectiveOperationException e){return 104;}}
}'''
driver='''import net.minecraft.test.ReflectMethodDemo;public class ReflectMethodDriver{public static void main(String[]a){for(String s:a)System.out.println(ReflectMethodDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-reflect-method-') as t:
 d=pathlib.Path(t);(d/'ReflectMethodDemo.java').write_text(source);(d/'ReflectMethodDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ReflectMethodDemo.java'),str(d/'ReflectMethodDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ReflectMethodDemo'];cl='net/minecraft/test/ReflectMethodDemo$Target';arg='net/minecraft/test/ReflectMethodDemo$Arg';entries=[f'{cl}#echo#(L{arg};)Ljava/lang/String;',f'{cl}#fail#(L{arg};)V',f'{cl}#zero#()Ljava/lang/String;'];env=dict(os.environ,MC_AOT_REFLECT_METHODS='|'.join(entries))
 p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(i) for i in range(8)]*12;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ReflectMethodDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','8'],capture_output=True,text=True)
 if p.returncode!=2 or 'Class.getMethod: método no registrado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 p=subprocess.run(base+[str(d/'unregistered'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 p=subprocess.run([str(d/'unregistered'),'0','0'],capture_output=True,text=True)
 if p.returncode!=2 or 'Class.getMethod: método no registrado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 for bad in ['x#y#)',f'{cl}#echo#(I)V']:
  p=subprocess.run(base+[str(d/'bad'),'run','(I)I'],capture_output=True,text=True,env=dict(os.environ,MC_AOT_REFLECT_METHODS=bad))
  if p.returncode==0:raise AssertionError(bad)
 print(f'OK: {len(vals)} invocaciones Java, null, parámetros, retorno y causa; métodos desconocidos y registros inválidos se rechazan')
