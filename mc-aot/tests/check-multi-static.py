#!/usr/bin/env python3
"""Inicialización monohilo acotada de tres clases con ciclo y estado compartido."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class Root {
 public static final int CONST=13;
 public static int first=Other.value;
 public static int later=9;
 public static int trace=Other.add(4);
 public static int peek(){return first;}
 public static int result(){return first*1000+later*100+trace;}
 public static int other(){return Other.value;}
 public static int seen(){return Other.seen;}
 public static int change(int n){Other.value+=n;return Other.value;}
 public static long third(long n){return Third.increment(n);}
 public static int thirdInit(){return Third.count;}
 public static int narrow(int n){Other.small=(byte)n;Other.letter=(char)n;Other.shortValue=(short)n;Other.flag=(n&1)!=0;return Other.small+Other.letter+Other.shortValue+(Other.flag?1:0);}
}
class Other {static int value=Root.later+3;static int seen=Root.peek();static byte small;static char letter;static short shortValue;static boolean flag;static int add(int n){value+=n;return value;}}
class Third {static int count=init();static long value=Root.first+100L;static int init(){Root.later+=100;return 1;}static long increment(long n){value+=n;return value;}}
'''
driver='''import net.minecraft.test.Root;
public class MultiStaticReference {
 public static void main(String[] args){for(int i=0;i<args.length;){int op=Integer.parseInt(args[i++]);switch(op){
 case 0->System.out.println(Root.result());case 1->System.out.println(Root.other());case 2->System.out.println(Root.seen());
 case 3->System.out.println(Root.change(Integer.parseInt(args[i++])));case 4->System.out.println(Root.third(Long.parseLong(args[i++])));
 case 5->System.out.println(Root.thirdInit());case 6->System.out.println(Root.class.getField("CONST").getInt(null));case 7->System.out.println(Root.narrow(Integer.parseInt(args[i++])));
 default->throw new IllegalArgumentException();}}}
}'''.replace('main(String[] args){','main(String[] args) throws Exception{')
with tempfile.TemporaryDirectory(prefix='mc-multi-static-') as tmp:
 d=pathlib.Path(tmp);(d/'Root.java').write_text(source);(d/'MultiStaticReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'Root.java'),str(d/'MultiStaticReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('result','()I'),('other','()I'),('seen','()I'),('change','(I)I'),('third','(J)J'),('thirdInit','()I'),('@CONST','I'),('narrow','(I)I')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Root',str(d/'native')]
 for n,desc in specs:cmd.extend([n,desc])
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 empty=subprocess.run([str(d/'native')],capture_output=True,text=True,check=True)
 if empty.stdout:raise AssertionError(('ejecución vacía inicializó clase',empty.stdout))
 rng=random.Random(778);commands=['0','1','2','6','5','4','0'];ops=6
 for _ in range(250):
  op=rng.randrange(len(specs));commands.append(str(op));ops+=1
  if op in (3,7):commands.append(str(rng.choice([-2147483648,-1,0,1,2147483647,rng.randint(-100000,100000)])))
  if op==4:commands.append(str(rng.choice([-9223372036854775808,-1,0,1,9223372036854775807,rng.randint(-100000,100000)])))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'MultiStaticReference',*commands],capture_output=True,text=True,check=True).stdout.splitlines()
 native=subprocess.run([str(d/'native'),*commands],capture_output=True,text=True,check=True).stdout.splitlines()
 if len(java)!=ops or java!=native:raise AssertionError((len(java),len(native),next(((i,a,b) for i,(a,b) in enumerate(zip(java,native)) if a!=b),None)))
 if java[:6]!=['3907','7','0','13','1','103']:raise AssertionError(('semántica del ciclo',java[:6]))
 print(f'OK: {ops} operaciones Java; 3 clases, inicialización perezosa una vez, ciclo, campos preparados, ConstantValue, tipos estrechos y estado compartido')
