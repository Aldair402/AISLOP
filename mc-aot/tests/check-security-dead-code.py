#!/usr/bin/env python3
"""Rama SecurityManager inalcanzable bajo Java 25; referencia virtual alcanzable se rechaza."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
@SuppressWarnings("removal") public class DeadSecurity {
 public static int run(int n){SecurityManager s=System.getSecurityManager();if(s!=null){Runnable x=()->System.out.println("imposible");x.run();return -1;}return n+7;}
 public static int run2(int n){SecurityManager s=System.getSecurityManager();if(s==null)return n+9;Runnable x=()->System.out.println("imposible");x.run();return -1;}
 public static int direct(int n){if(System.getSecurityManager()!=null){Runnable x=()->System.out.println("imposible");x.run();return -1;}return n+11;}
 public static int unsupported(){java.util.function.Function<String,String> x=String::toUpperCase;return x.apply("real").length();}
}'''
driver='''import net.minecraft.test.DeadSecurity;public class DeadDriver{public static void main(String[] a){for(String x:a){int n=Integer.parseInt(x);System.out.println(DeadSecurity.run(n));System.out.println(DeadSecurity.run2(n));System.out.println(DeadSecurity.direct(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-security-fold-') as t:
 d=pathlib.Path(t);(d/'DeadSecurity.java').write_text(source);(d/'DeadDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DeadSecurity.java'),str(d/'DeadDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DeadSecurity']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I','run2','(I)I','direct','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=['-100','0','1','100','2147483647']*10;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DeadDriver',*vals],capture_output=True,text=True,check=True).stdout;args=[v for n in vals for v in ('0',n,'1',n,'2',n)];native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run(base+[str(d/'bad'),'unsupported','()I'],capture_output=True,text=True)
 if p.returncode==0 or 'lambda método JDK no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)*3} resultados Java 25; invokedynamic inalcanzable podado conservadoramente y alcanzable rechazado')
