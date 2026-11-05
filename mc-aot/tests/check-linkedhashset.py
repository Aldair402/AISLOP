#!/usr/bin/env python3
"""LinkedHashSet limitado a String/null: orden, igualdad e iteración fail-fast."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class SetDemo {
 public static int run(String x,int n){Set<String>s=new LinkedHashSet<>();s.add("a");s.add(null);try{switch(n){
 case 0:return (s.add(x)?1:0)+s.size()*10+(s.contains(x)?100:0);
 case 1:s.add("b");Iterator<String>i=s.iterator();return i.next().equals("a")&&i.next()==null&&i.next().equals("b")&&!i.hasNext()?1:0;
 case 2:Iterator<String>a=s.iterator();s.add("a");return a.next().equals("a")?2:0;
 case 3:Iterator<String>b=s.iterator();s.add("b");return b.hasNext()?(b.next()==null?0:-1):-2;
 case 4:Iterator<String>c=s.iterator();s.remove("a");return c.hasNext()?(c.next()==null?0:-1):-2;
 case 5:return (s.remove(x)?1:0)+(s.remove(x)?2:0)+s.size()*10;
 case 6:s.clear();Iterator<String>z=s.iterator();s.clear();return z.next()==null?0:-1;
 case 7:Iterator<String>k=s.iterator();k.next();k.next();return k.next()==null?0:-1;
 case 8:s.clear();return s.isEmpty()?8:0;
 case 9:Collection<String>q=s;return q.contains("a")&&q.remove("a")&&!q.contains("a")?9:0;
 case 10:Set<Object> bad=new LinkedHashSet<>();bad.add(new Object());return -1;
 default:return 99;
 }}catch(ConcurrentModificationException e){return 101;}catch(NoSuchElementException e){return 102;}}
}'''
driver='''import net.minecraft.test.SetDemo;public class SetDriver{public static void main(String[] a){for(int i=0;i<a.length;i+=2){String x=a[i].equals("@null")?null:a[i];System.out.println(SetDemo.run(x,Integer.parseInt(a[i+1])));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-set-') as t:
 d=pathlib.Path(t);(d/'SetDemo.java').write_text(source);(d/'SetDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SetDemo.java'),str(d/'SetDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SetDemo',str(d/'native'),'run','(Ljava/lang/String;I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[(x,str(n)) for x in ('@null','a','b','á') for n in range(10)]*3
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SetDriver',*[v for pair in vals for v in pair]],capture_output=True,text=True,check=True).stdout
 args=[v for x,n in vals for v in ('0','null' if x=='@null' else 's:'+x,n)];native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'0','s:x','10'],capture_output=True,text=True)
 if p.returncode!=2 or 'solo String/null soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} operaciones Java LinkedHashSet String/null, igualdad, orden, alias e iterador fail-fast; otros tipos abortan')
