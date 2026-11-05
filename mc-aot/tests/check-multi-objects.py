#!/usr/bin/env python3
"""Objetos concretos acotados en el heap multiclase y clase real FeatureFlagUniverse."""
import os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];base=root.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=base/'downloads/server-26.3-inner.jar'
source='''package net.minecraft.test;
import net.minecraft.world.flag.FeatureFlagUniverse;
public class ObjectsDemo {
 static Box first,alias,other;static FeatureFlagUniverse feature;static Object token;static CharSequence textRef;static Object textAlias,vector;
 public static void make(int n,String s){first=new Box(n,s);alias=first;other=new Box(n+1,s);token=new Object();}
 public static int read(){return alias.get()+other.get()+Box.created;}
 public static int change(int n){alias.set(n);return first.get();}
 public static int identity(){return (first==alias?1:0)+(first==other?2:0)+(token==null?4:0)+(first.self()==alias?8:0);}
 public static void clear(){first=null;alias=null;other=null;feature=null;token=null;}
 public static int empty(){return (first==null?1:0)+(alias==null?2:0)+(feature==null?4:0)+(token==null?8:0);}
 public static void mix(String s){textRef=s;textAlias=textRef;vector=new int[2];}
 public static int mixed(){return (textRef==textAlias?1:0)+(textRef==null?2:0)+(vector==null?4:0);}
 public static void makeFeature(String s){feature=new FeatureFlagUniverse(s);}
 public static String value(){return feature.toString();}
}
class Box {
 static int created=10;int n;String s;int[] values;Box next;long large;char ch;Object obj;
 Box(int x,String text){n=x;s=text;values=new int[2];values[0]=x;large=x;ch=(char)x;obj=text;created++;}
 int get(){return n+values[0]+(int)large+ch+(obj==s?1:0);}
 void set(int x){n=x;values[0]=x;large=x;ch=(char)x;}
 Box self(){return this;}
}
'''
driver='''import net.minecraft.test.ObjectsDemo;
public class ObjectsDriver {public static void main(String[] a){ObjectsDemo.clear();System.out.println("OK");System.out.println(ObjectsDemo.empty());for(String x:a){int n=Integer.parseInt(x);ObjectsDemo.make(n,"abc");System.out.println("OK");System.out.println(ObjectsDemo.read());System.out.println(ObjectsDemo.change(~n));System.out.println(ObjectsDemo.identity());}ObjectsDemo.mix("abc");System.out.println("OK");System.out.println(ObjectsDemo.mixed());ObjectsDemo.mix(null);System.out.println("OK");System.out.println(ObjectsDemo.mixed());ObjectsDemo.makeFeature("abc");System.out.println("OK");System.out.println(ObjectsDemo.value());ObjectsDemo.makeFeature(null);System.out.println("OK");System.out.println(ObjectsDemo.value());}}'''
with tempfile.TemporaryDirectory(prefix='mc-multi-objects-') as tmp:
 d=pathlib.Path(tmp);(d/'ObjectsDemo.java').write_text(source);(d/'ObjectsDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(jar),'-d',str(d),str(d/'ObjectsDemo.java'),str(d/'ObjectsDriver.java')],check=True)
 with zipfile.ZipFile(jar) as z:
  data=z.read('net/minecraft/world/flag/FeatureFlagUniverse.class');path=d/'net/minecraft/world/flag/FeatureFlagUniverse.class';path.parent.mkdir(parents=True);path.write_bytes(data)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('clear','()V'),('empty','()I'),('make','(ILjava/lang/String;)V'),('read','()I'),('change','(I)I'),('identity','()I'),('makeFeature','(Ljava/lang/String;)V'),('value','()Ljava/lang/String;'),('mix','(Ljava/lang/String;)V'),('mixed','()I')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ObjectsDemo',str(d/'native')]
 for name,desc in specs:cmd +=[name,desc]
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(419);values=[-2147483648,-65537,-1,0,1,65535,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(50)]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ObjectsDriver',*map(str,values)],capture_output=True,text=True,check=True).stdout.splitlines()
 args=['0','1']
 for n in values:args += ['2',str(n),'s:abc','3','4',str(~n),'5']
 args += ['8','s:abc','9','8','null','9','6','s:abc','7','6','null','7']
 native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout.splitlines()
 if java!=native:raise AssertionError(next(((i,a,b) for i,(a,b) in enumerate(zip(java,native)) if a!=b),('longitud',len(java),len(native))))
 print(f'OK: {len(java)} operaciones Java con objetos, campos, alias, identidad, llamadas de instancia, referencias externas y FeatureFlagUniverse real')
