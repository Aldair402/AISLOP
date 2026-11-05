#!/usr/bin/env python3
"""ArrayList.stream: construcción perezosa, encadenado y guardas, sin terminales."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.stream.*;
public class ListStreamProbe {
 static int calls;static boolean accepts(Object x){calls++;return true;}
 public static int run(int n){try{Collection<String> xs=n==9?null:new ArrayList<>();if(n==9){xs.stream();return -1;}xs.add("a");Stream<String> a=xs.stream();xs.add("b");Stream<String> b=a.filter(ListStreamProbe::accepts);if((n&1)!=0)try{a.filter(ListStreamProbe::accepts);return -2;}catch(IllegalStateException e){}if((n&2)!=0)try{b.filter(null);return -3;}catch(NullPointerException e){}if((n&4)!=0){b.close();try{b.filter(ListStreamProbe::accepts);return -4;}catch(IllegalStateException e){}}b.close();return calls+xs.size()+(b.isParallel()?100:10);}catch(NullPointerException e){return 20;}}
 public static int virtual(int n){ArrayList<String> a=new ArrayList<>();return a.stream().isParallel()?1:2;}
 public static int unsupported(int n){Collection<?> xs=new Properties().entrySet();return xs.stream().isParallel()?1:2;}
}'''
driver='''import net.minecraft.test.ListStreamProbe;public class Driver{public static void main(String[] a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("run")?ListStreamProbe.run(n):ListStreamProbe.virtual(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-list-stream-') as temp:
 d=pathlib.Path(temp);(d/'ListStreamProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ListStreamProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ListStreamProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError(p.stderr)
 def compare(method,seq):
  compile(method);j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',method,*map(str,seq)],capture_output=True,text=True,check=True,timeout=30);n=subprocess.run([str(d/method),*[v for i in seq for v in ('0',str(i))]],capture_output=True,text=True,timeout=30)
  if n.returncode or j.stdout!=n.stdout:raise AssertionError((method,j.stdout,n.stdout,n.stderr))
 vals=list(range(-40,41));compare('run',vals);compare('virtual',vals);compile('unsupported');n=subprocess.run([str(d/'unsupported'),'0','0'],capture_output=True,text=True,timeout=30)
 if n.returncode==0 or 'Collection.stream: fuente fuera del perfil' not in n.stderr:raise AssertionError((n.returncode,n.stderr))
 print(f'OK: {len(vals)*2} resultados ArrayList.stream secuencial y perezoso, cierre, estado y null; otras fuentes abortan; sin terminales')
