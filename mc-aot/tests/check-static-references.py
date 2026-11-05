#!/usr/bin/env python3
"""Campos estáticos String/arrays, internado y alias entre clases frente a Java."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;
public class ReferenceState {
 public static final String CONSTANT="cadena🚀";
 static String first=OtherState.first;
 static String later="ready";
 static int[] numbers={2,3};
 static String[] words={"old",null,"🚀"};
 public static int sameLiteral(){return first==CONSTANT?1:0;}
 public static int otherSawNull(){return OtherState.sawNull;}
 public static String getLater(){return later;}
 public static void setLater(String s){later=s;}
 public static void bind(){OtherState.bind();}
 public static int step(int n){numbers[0]+=n;return OtherState.numbers[0];}
 public static int setWord(String s){words[0]=s;return OtherState.words[0]==s?(s==null?-1:s.length()):-2;}
 public static int replace(){words=new String[]{"new"};return OtherState.words==words?1:0;}
 public static int oldWordLength(){String v=OtherState.words[0];return v==null?-1:v.length();}
 public static int primitiveLength(){return numbers.length;}
}
class OtherState {
 static int sawNull=ReferenceState.later==null?1:0;
 static String first=ReferenceState.later==null?ReferenceState.CONSTANT:"bad";
 static int[] numbers;static String[] words;
 static void bind(){numbers=ReferenceState.numbers;words=ReferenceState.words;}
}'''
driver='''import net.minecraft.test.ReferenceState;
public class StaticReferenceDriver {
 public static void main(String[] args)throws Exception {for(int i=0;i<args.length;){int op=Integer.parseInt(args[i++]);switch(op){
 case 0->System.out.println(ReferenceState.sameLiteral());case 1->System.out.println(ReferenceState.otherSawNull());
 case 2->System.out.println(ReferenceState.getLater());case 3->{String s=args[i++];ReferenceState.setLater(s.equals("N")?null:s);System.out.println("OK");}
 case 4->{ReferenceState.bind();System.out.println("OK");}case 5->System.out.println(ReferenceState.step(Integer.parseInt(args[i++])));
 case 6->{String s=args[i++];System.out.println(ReferenceState.setWord(s.equals("N")?null:s));}
 case 7->System.out.println(ReferenceState.replace());case 8->System.out.println(ReferenceState.oldWordLength());
 case 9->System.out.println(ReferenceState.primitiveLength());case 10->System.out.println(ReferenceState.class.getField("CONSTANT").get(null));
 default->throw new IllegalArgumentException();}}}
}'''
with tempfile.TemporaryDirectory(prefix='mc-static-refs-') as tmp:
 d=pathlib.Path(tmp);(d/'ReferenceState.java').write_text(source,encoding='utf8');(d/'StaticReferenceDriver.java').write_text(driver,encoding='utf8')
 subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-d',str(d),str(d/'ReferenceState.java'),str(d/'StaticReferenceDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('sameLiteral','()I'),('otherSawNull','()I'),('getLater','()Ljava/lang/String;'),('setLater','(Ljava/lang/String;)V'),('bind','()V'),('step','(I)I'),('setWord','(Ljava/lang/String;)I'),('replace','()I'),('oldWordLength','()I'),('primitiveLength','()I'),('@CONSTANT','Ljava/lang/String;')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ReferenceState',str(d/'native')]
 for n,desc in specs:cmd.extend([n,desc])
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(111);ops=[(0,None),(1,None),(10,None),(2,None),(4,None),(5,5),(6,'🚀'),(8,None),(7,None),(8,None),(4,None),(8,None)];
 for _ in range(200):
  op=rng.choice([0,1,2,3,4,5,6,7,8,9,10]);arg=None
  if op==5:arg=str(rng.choice([-2147483648,-1,0,1,2147483647,rng.randint(-10000,10000)]))
  if op in (3,6):arg=rng.choice(['N','hola','🚀','abc','null'])
  ops.append((op,arg))
 java=[];native=[]
 for op,arg in ops:
  java.append(str(op));native.append(str(op))
  if arg is not None:
   arg=str(arg);java.append(arg);native.append(('null' if arg=='N' else 's:'+arg) if op in (3,6) else arg)
 expected=subprocess.run([str(jdk/'java'),'-cp',str(d),'StaticReferenceDriver',*java],capture_output=True,text=True,check=True).stdout.splitlines()
 got=subprocess.run([str(d/'native'),*native],capture_output=True,text=True,check=True).stdout.splitlines()
 if len(expected)!=len(ops) or got!=expected:raise AssertionError((len(expected),len(got),next(((i,a,b) for i,(a,b) in enumerate(zip(expected,got)) if a!=b),None)))
 if expected[:5]!=['1','1','cadena🚀','ready','OK']:raise AssertionError(expected[:5])
 # Array diagnostics preserve null and exact UTF-16 code units.
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ReferenceState',str(d/'array'),'@words','[Ljava/lang/String;'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 diag=subprocess.run([str(d/'array'),'0'],capture_output=True,text=True,check=True).stdout.strip()
 if diag!='sarr16:[x006f006c0064,n,xd83dde80]':raise AssertionError(('array diag',diag))
 print(f'OK: {len(ops)} operaciones Java en 2 clases; String ConstantValue, null, UTF-16, referencias de arrays y alias compartido')
