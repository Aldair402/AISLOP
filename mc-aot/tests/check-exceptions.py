#!/usr/bin/env python3
"""Compara excepciones Java representadas y sus manejadores con JVM 25."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
fixture=r'''package net.minecraft.test;
public class ExceptionFixture {
 public static int caught(int n){try{return 42/n;}catch(ArithmeticException e){return 31;}}
 public static long caughtLong(long n){try{return Long.MIN_VALUE/n;}catch(ArithmeticException e){return 123;}}
 public static int exact(long n){try{return Math.toIntExact(n);}catch(ArithmeticException e){return -7;}}
 static int callee(int n){return 10/n;}
 public static int cross(int n){try{return callee(n);}catch(ArithmeticException e){return 45;}}
 public static int multiple(int n){try{int[] a=n<0?null:new int[]{10};return a[n];}catch(NullPointerException e){return -10;}catch(IndexOutOfBoundsException e){return -20;}}
 public static int rethrow(int n){try{return 12/n;}catch(ArithmeticException e){try{throw e;}catch(ArithmeticException f){return e==f?91:-1;}}}
 public static int finallyNested(int n){int[] state={0};try{try{return 24/n;}finally{state[0]++;}}catch(ArithmeticException e){return state[0]+80;}}
 public static int wrongCatch(int n){try{return 42/n;}catch(NullPointerException e){return -3;}}
 public static int nullThrow(int n){try{throw null;}catch(NullPointerException e){return e==null?-1:88;}}
 public static int strChar(String a,int i){try{return a.charAt(i);}catch(NullPointerException e){return -2;}catch(IndexOutOfBoundsException e){return -3;}}
 public static int negative(int n){try{return new int[n].length;}catch(NegativeArraySizeException e){return -4;}}
 public static int cast(int[] a){try{return ((String)(Object)a).length();}catch(ClassCastException e){return -5;}catch(NullPointerException e){return -6;}}
 public static int store(String[] a){try{Object[] x=a;x[0]=x;return 1;}catch(ArrayStoreException e){return -7;}catch(IndexOutOfBoundsException e){return -8;}catch(NullPointerException e){return -9;}}
 public static int explicit(int n){try{if(n==0)throw new IllegalArgumentException("bad");if(n<0)throw new NumberFormatException();return n;}catch(NumberFormatException e){return 21;}catch(IllegalArgumentException e){return 22;}}
 public static int hierarchy(int n){try{if(n<0)throw new java.io.IOException("io");if(n==0)throw new Exception();if(n==1)throw new Throwable();if(n==2)throw new RuntimeException();return 3;}catch(RuntimeException e){return 11;}catch(java.io.IOException e){return 12;}catch(Exception e){return 13;}catch(Throwable e){return 14;}}
 public static int disallowed(int n){try{return n+1;}catch(OutOfMemoryError e){return -1;}}
}'''
driver=r'''import java.io.*;import net.minecraft.test.ExceptionFixture;
public class ExceptionsReference {
 public static void main(String[] args)throws Exception{var in=new BufferedReader(new InputStreamReader(System.in));String line;
 while((line=in.readLine())!=null){String[] a=line.split(" ");try{String op=a[0],v=a[1];Object out=switch(op){
 case "caught"->ExceptionFixture.caught(Integer.parseInt(v)); case "caughtLong"->ExceptionFixture.caughtLong(Long.parseLong(v));
 case "exact"->ExceptionFixture.exact(Long.parseLong(v));case "cross"->ExceptionFixture.cross(Integer.parseInt(v));
 case "multiple"->ExceptionFixture.multiple(Integer.parseInt(v));case "rethrow"->ExceptionFixture.rethrow(Integer.parseInt(v));
 case "finallyNested"->ExceptionFixture.finallyNested(Integer.parseInt(v));case "wrongCatch"->ExceptionFixture.wrongCatch(Integer.parseInt(v));
 case "nullThrow"->ExceptionFixture.nullThrow(Integer.parseInt(v));case "negative"->ExceptionFixture.negative(Integer.parseInt(v));
 case "explicit"->ExceptionFixture.explicit(Integer.parseInt(v));case "hierarchy"->ExceptionFixture.hierarchy(Integer.parseInt(v));
 case "strChar"->ExceptionFixture.strChar(v.equals("null")?null:v.equals("empty")?"":"🚀",Integer.parseInt(a[2]));
 case "cast"->ExceptionFixture.cast(v.equals("null")?null:new int[1]);
 case "store"->ExceptionFixture.store(v.equals("null")?null:new String[Integer.parseInt(v)]);
 default->throw new IllegalArgumentException();};System.out.println(out);
 }catch(Throwable e){System.out.println("EX:"+e.getClass().getSimpleName());}}
 }
}'''
with tempfile.TemporaryDirectory(prefix='mc-exceptions-') as temp:
 d=pathlib.Path(temp);(d/'ExceptionFixture.java').write_text(fixture,encoding='utf8');(d/'ExceptionsReference.java').write_text(driver,encoding='utf8')
 subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-d',str(d),str(d/'ExceptionFixture.java'),str(d/'ExceptionsReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 specs={n:'(I)I' for n in ['caught','cross','multiple','rethrow','finallyNested','wrongCatch','nullThrow','negative','explicit','hierarchy']}
 specs.update({'caughtLong':'(J)J','exact':'(J)I','strChar':'(Ljava/lang/String;I)I','cast':'([I)I','store':'([Ljava/lang/String;)I'})
 for label,desc in specs.items():
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'test.jar'),'net/minecraft/test/ExceptionFixture',label,desc,str(d/label)],capture_output=True,text=True)
  if p.returncode:raise RuntimeError((label,p.stderr))
 cases=[]
 for name in ['caught','cross','multiple','rethrow','finallyNested','wrongCatch','nullThrow','negative','explicit','hierarchy']:
  for x in [-3,-1,0,1,2,3,10]:cases.append((name,[str(x)],[str(x)]))
 for name in ['caughtLong','exact']:
  for x in [-9223372036854775808,-2147483649,-1,0,1,2147483647,2147483648,9223372036854775807]:cases.append((name,[str(x)],[str(x)]))
 for v,native in [('null','null'),('empty','s:'),('rocket','s:🚀')]:
  for idx in [-1,0,1,2,3]:cases.append(('strChar',[v,str(idx)],[native,str(idx)]))
 for v,native in [('null','null'),('x','[1]')]:cases.append(('cast',[v],[native]))
 for v,native in [('null','null'),('0','sarr:[]'),('1','sarr:[n]')]:cases.append(('store',[v],[native]))
 inp=''.join(' '.join([name,*java])+'\n' for name,java,_ in cases)
 ref=subprocess.run([str(jdk/'java'),'-cp',str(d),'ExceptionsReference'],input=inp,capture_output=True,text=True,check=True).stdout.splitlines()
 if len(ref)!=len(cases):raise AssertionError((len(ref),len(cases)))
 for (name,java,native),expected in zip(cases,ref):
  got=subprocess.run([str(d/name),*native],capture_output=True,text=True)
  if expected.startswith('EX:'):
   if got.returncode!=2 or expected[3:] not in got.stderr:raise AssertionError((name,java,expected,got.returncode,got.stdout,got.stderr))
  elif got.returncode or got.stdout.strip()!=expected:raise AssertionError((name,java,expected,got.returncode,got.stdout,got.stderr))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'test.jar'),'net/minecraft/test/ExceptionFixture','disallowed','(I)I',str(d/'bad')],capture_output=True,text=True)
 if p.returncode==0 or 'tipo catch no soportado' not in p.stderr or (d/'bad').exists():raise AssertionError(('catch no soportado',p.stdout,p.stderr))
 print(f'OK: {len(cases)} casos Java; catch por tipo, orden, propagación, finally, new, constructores, athrow e identidad; catch no soportado rechazado')
