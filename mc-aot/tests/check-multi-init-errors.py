#!/usr/bin/env python3
"""Primera inicialización fallida, clase errónea, catch y Error directo, monohilo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class InitErrors {
 static Error marker=new Error();
 public static int broken(){try{return Broken.f();}catch(ArithmeticException e){return -1;}catch(ExceptionInInitializerError e){return 11;}catch(NoClassDefFoundError e){return 12;}}
 public static int direct(){try{return BrokenError.f();}catch(NoClassDefFoundError e){return 22;}catch(ExceptionInInitializerError e){return -2;}catch(Error e){return e==marker?21:-3;}}
 public static int parent(){try{return Parent.f();}catch(ExceptionInInitializerError e){return 31;}catch(NoClassDefFoundError e){return 32;}}
 public static int child(){try{return Child.f();}catch(ExceptionInInitializerError e){return 41;}catch(NoClassDefFoundError e){return 42;}}
 public static int caught(){return Safe.f();}
 public static int instance(){return new Worker().run();}
}
class Broken {static int n=10/zero();static int zero(){return 0;}static int f(){return n;}}
class BrokenError {static {if(yes())throw InitErrors.marker;}static boolean yes(){return true;}static int f(){return 0;}}
class Child {static int n=10/zero();static int zero(){return 0;}static int f(){return n;}}
class Parent {static int n=Child.f();static int f(){return n;}}
class Safe {static int n;static {try {n=10/zero();}catch(ArithmeticException e){n=7;}}static int zero(){return 0;}static int f(){return n;}}
class Worker {int run(){try{return 10/zero();}catch(ArithmeticException e){return 9;}}int zero(){return 0;}}
'''
driver='''import net.minecraft.test.InitErrors;public class InitErrorsDriver{public static void main(String[] x){System.out.println(InitErrors.broken());System.out.println(InitErrors.broken());System.out.println(InitErrors.direct());System.out.println(InitErrors.direct());System.out.println(InitErrors.parent());System.out.println(InitErrors.parent());System.out.println(InitErrors.child());System.out.println(InitErrors.caught());System.out.println(InitErrors.caught());System.out.println(InitErrors.instance());}}'''
with tempfile.TemporaryDirectory(prefix='mc-init-errors-') as t:
 d=pathlib.Path(t);(d/'InitErrors.java').write_text(source);(d/'InitErrorsDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InitErrors.java'),str(d/'InitErrorsDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/InitErrors',str(d/'native'),'broken','()I','direct','()I','parent','()I','child','()I','caught','()I','instance','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'InitErrorsDriver'],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),'0','0','1','1','2','2','3','4','4','5'],capture_output=True,text=True,check=True).stdout
 if java!=native or java!='11\n12\n21\n22\n31\n32\n42\n7\n7\n9\n':raise AssertionError((java,native))
 print('OK: 10 operaciones Java: ExceptionInInitializerError, NoClassDefFoundError, Error directo conserva identidad, fallos anidados y handlers monohilo')
