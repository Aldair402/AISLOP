#!/usr/bin/env python3
"""Arrays Object[]/Class[] y covarianza String[] comparados con Java."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class ObjectArrayDemo {
 static Object[] a=new Object[5];static String[] s=new String[2];static Class<?>[] c=new Class<?>[2];static Object marker=new Object();static int[] ints=new int[2];
 static Object[] alias(Object[] x){return x;}static Class<?>[] classes(){return c;}static void put(Object[] a,int i,Object v){a[i]=v;}
 public static int run(int n){try {switch(n){
 case 0:put(a,0,"hola");put(a,1,marker);put(a,2,ints);put(a,3,s);put(a,4,c);return a.length+(a[0]=="hola"?10:0)+(a[1]==marker?20:0)+(a[2]==ints?30:0)+(a[3]==s?40:0)+(a[4]==c?50:0);
 case 1:put(alias(s),0,"ok");put(alias(s),1,null);return s[0]=="ok"&&s[1]==null?1:0;
 case 2:put(alias(c),0,ObjectArrayDemo.class);put(alias(c),1,String.class);return classes()[0]==ObjectArrayDemo.class&&classes()[1]==String.class?2:0;
 case 3:put(alias(s),0,marker);return -1;
 case 4:put(alias(c),0,"wrong");return -1;
 case 5:put(alias(s),-1,marker);return -1;
 case 6:put(null,0,marker);return -1;
 case 7:Object[] t=(Object[])(Object)s;return t==s?7:0;
 case 8:Object[] u=(Object[])(Object)c;return u==c?8:0;
 case 9:Object[] v=(Object[])(Object)ints;return -1;
 case 10:Class<?>[] w=(Class<?>[])(Object)s;return -1;
 case 11:Class<?>[] q=(Class<?>[])(Object)c;return q==c?11:0;
 case 12:Class<?>[] z=(Class<?>[])(Object)null;return z==null?12:0;
 case 13:Object[] neg=new Object[-1];return neg.length;
 default:return 99;
 }}catch(ArrayStoreException e){return 101;}catch(ArrayIndexOutOfBoundsException e){return 102;}catch(NullPointerException e){return 103;}catch(ClassCastException e){return 104;}catch(NegativeArraySizeException e){return 105;}}
}'''
driver='''import net.minecraft.test.ObjectArrayDemo;public class ObjectArrayDriver{public static void main(String[] a){for(String s:a)System.out.println(ObjectArrayDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-object-arrays-') as t:
 d=pathlib.Path(t);(d/'ObjectArrayDemo.java').write_text(source);(d/'ObjectArrayDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ObjectArrayDemo.java'),str(d/'ObjectArrayDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ObjectArrayDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(14))*8+[-1,14]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ObjectArrayDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: {len(vals)} operaciones Java: Object[] y Class[], alias String[], covarianza, null, casts y prioridad de excepciones')
