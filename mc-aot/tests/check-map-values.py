#!/usr/bin/env python3
"""Vista de ConcurrentHashMap y copia ArrayList(Collection), sin concurrencia."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;import java.util.concurrent.*;public class MapValuesDemo {
 static Map<String,String> map=new ConcurrentHashMap<>();static Collection<String> view=map.values();
 public static int run(String key,int n){try{switch(n){case 0:map.put(key,key);return view.size();case 1:List<String>a=new ArrayList<>(view);int h=1;for(int i=0;i<a.size();i++)h=h*31+a.get(i).hashCode();return h;case 2:return map.values()==view?2:0;case 3:map.remove(key);return view.size();case 4:view.clear();return map.size();case 5:Collection<String> empty=null;List<String>b=new ArrayList<>(empty);return b.size();default:return 99;}}catch(NullPointerException e){return 105;}}
}'''
# String.hashCode es necesario para comparar orden de forma determinista.
driver='''import net.minecraft.test.MapValuesDemo;public class MapValuesDriver{public static void main(String[] a){for(int i=0;i<a.length;i+=2)System.out.println(MapValuesDemo.run(a[i],Integer.parseInt(a[i+1])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-map-values-') as t:
 d=pathlib.Path(t);(d/'MapValuesDemo.java').write_text(source);(d/'MapValuesDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'MapValuesDemo.java'),str(d/'MapValuesDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/MapValuesDemo',str(d/'native'),'run','(Ljava/lang/String;I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 random.seed(41);keys=['k'+str(i)+random.choice('abcdef') for i in range(70)];ops=[]
 for k in keys:ops.extend([(k,'0'),(k,'1')])
 ops += [('x','2')]+[(k,'3') for k in keys[::3]]+[('x','1'),('x','4'),('x','1'),('x','5')]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'MapValuesDriver',*[v for pair in ops for v in pair]],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*[v for x,n in ops for v in ('0','s:'+x,n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 keys=[''.join('BB' if i&(1<<bit) else 'Aa' for bit in range(4)) for i in range(9)];args=[v for k in keys for v in ('0','s:'+k,'0')]+['0','s:x','1'];p=subprocess.run([str(d/'native'),*args],capture_output=True,text=True)
 if p.returncode!=2 or 'colisiones complejas no soportadas' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(ops)} operaciones Java de Map.values y copia ordenada tras inserciones, resize, eliminación, null y clear; colisiones complejas se rechazan')
