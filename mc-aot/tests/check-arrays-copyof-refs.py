#!/usr/bin/env python3
"""Arrays.copyOf(Object[],int): clase, identidad, longitud, relleno y excepciones."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.Arrays;public class CopyOfProbe{static final class K{} public static int run(int n){int size=n%8-2,kind=(n/8)%4;Object[] a=kind==0?null:kind==1?new String[]{"a",null,"b"}:kind==2?new Object[]{"a",new K(),null}:new Class<?>[]{String.class,Object.class};try{Object[] c=Arrays.copyOf(a,size);int v=c.length*17+(c!=a?1:0)+(c.getClass()==a.getClass()?2:0);for(int i=0;i<c.length;i++){if(c[i]==null)v+=5;else if(i<a.length&&c[i]==a[i])v+=7;}if(c.length>0){c[0]=null;if(a.length>0&&a[0]!=null)v+=11;}return v;}catch(NullPointerException e){return -9;}catch(NegativeArraySizeException e){return -500+e.getMessage().hashCode();}}
 public static int project(int n){K k=new K();K[] a=new K[]{k,null};K[] b=Arrays.copyOf(a,n%6);int v=b.length*10+(b!=a?1:0)+(b instanceof K[]?2:0);for(int i=0;i<b.length;i++){if(b[i]==null)v+=3;else if(b[i]==k)v+=7;}return v;}
 public static int over(int n){return Arrays.copyOf(new Object[0],1000001).length;}}
'''
driver='''import net.minecraft.test.CopyOfProbe;public class Driver{public static void main(String[]a){for(String n:a){int x=Integer.parseInt(n);System.out.println(CopyOfProbe.run(x));System.out.println(CopyOfProbe.project(x));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-copyof-') as t:
 d=pathlib.Path(t);(d/'CopyOfProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'CopyOfProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(m):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/CopyOfProbe',str(d/m),m,'(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError(p.stderr)
 compile('run');compile('project');compile('over');seq=list(range(128));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;parts=[subprocess.run([str(d/m),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines() for m in ('run','project')];n='\n'.join(v for pair in zip(*parts) for v in pair)+'\n'
 if j!=n:raise AssertionError([(i,a,b) for i,(a,b) in enumerate(zip(j.splitlines(),n.splitlines())) if a!=b])
 p=subprocess.run([str(d/'over'),'0','0'],capture_output=True,text=True)
 if p.returncode==0 or 'Arrays.copyOf: límite experimental' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(seq)*2} resultados Arrays.copyOf para String[], Object[], Class[], clases propias finales y null; guarda de límite')
