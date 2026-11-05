#!/usr/bin/env python3
"""Compara inicialización, campos estáticos y estado persistente de una clase con Java 25."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class Stateful {
 public static int counter;
 public static int initialized;
 public static long large;
 public static byte small;
 public static char letter;
 public static short shortValue;
 public static boolean flag;
 public static final int CONST=2000000000;
 public static final long CONST_LONG=9223372036854775807L;
 static { initialized++; counter=seed(11); large=0x123456789abcdefL; small=-120; letter=(char)65530; shortValue=-30000; flag=true; }
 static int seed(int x){return x*3+initialized;}
 public static int next(int x){counter+=x;return counter;}
 public static int current(){return counter;}
 public static int inits(){return initialized;}
 public static void add(int x){counter+=x;}
 public static long step(long x){large+=x;return large;}
 public static int narrow(int x){small=(byte)x;letter=(char)x;shortValue=(short)x;return small+letter+shortValue;}
 public static int toggle(boolean x){flag=x;return flag?1:0;}
 public static int emptyVoid(int x){noop(x);return x;}
 static void noop(int x){int y=x+1;}
}'''
driver='''import net.minecraft.test.Stateful;
public class StatefulReference {
 public static void main(String[] a) {for(int i=0;i<a.length;){String c=a[i++];switch(c){
 case "0" -> System.out.println(Stateful.next(Integer.parseInt(a[i++])));
 case "1" -> System.out.println(Stateful.current());
 case "2" -> System.out.println(Stateful.inits());
 case "3" -> {Stateful.add(Integer.parseInt(a[i++]));System.out.println("OK");}
 case "4" -> System.out.println(Stateful.step(Long.parseLong(a[i++])));
 case "5" -> System.out.println(Stateful.narrow(Integer.parseInt(a[i++])));
 case "6" -> System.out.println(Stateful.toggle(!a[i++].equals("0")));
 case "7" -> System.out.println(Stateful.emptyVoid(Integer.parseInt(a[i++])));
 default -> throw new IllegalArgumentException();
 }}}
}'''
with tempfile.TemporaryDirectory(prefix='mc-static-demo-') as tmp:
 d=pathlib.Path(tmp);(d/'Stateful.java').write_text(source);(d/'StatefulReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'Stateful.java'),str(d/'StatefulReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('next','(I)I'),('current','()I'),('inits','()I'),('add','(I)V'),('step','(J)J'),('narrow','(I)I'),('toggle','(Z)I'),('emptyVoid','(I)I')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','static-demo',str(d/'fixture.jar'),'net/minecraft/test/Stateful',str(d/'state')]
 for n,desc in specs:cmd.extend([n,desc])
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(9927);commands=['2','1','4','0','6','0','2'];ops=5
 for _ in range(350):
  op=rng.randrange(len(specs));commands.append(str(op));ops+=1
  if op in (0,3,5,7):commands.append(str(rng.choice([-2147483648,-1,0,1,2147483647,rng.randint(-2147483648,2147483647)])))
  elif op==4:commands.append(str(rng.choice([-9223372036854775808,-1,0,1,9223372036854775807,rng.randint(-9223372036854775808,9223372036854775807)])))
  elif op==6:commands.append(str(rng.randrange(2)))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'StatefulReference',*commands],capture_output=True,text=True,check=True).stdout.splitlines()
 native=subprocess.run([str(d/'state'),*commands],capture_output=True,text=True,check=True).stdout.splitlines()
 if len(java)!=ops or java!=native:raise AssertionError(('diferencia',len(java),len(native),next(((i,x,y) for i,(x,y) in enumerate(zip(java,native)) if x!=y),None)))
 for args in [['9'],['0'],['6','2']]:
  bad=subprocess.run([str(d/'state'),*args],capture_output=True,text=True)
  if bad.returncode==0:raise AssertionError(('entrada incorrecta aceptada',args))
 print(f'OK: inicializador una vez, 7 campos estáticos, void y {ops} operaciones secuenciales coinciden con Java 25; tres entradas inválidas rechazadas')
