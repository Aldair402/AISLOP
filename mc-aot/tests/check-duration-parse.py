#!/usr/bin/env python3
"""Duration.ofMillis y parseos restringidos comparados con Java 25."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.time.Duration;public class DurationDemo {
 public static long run(long n,int which){try{Duration d=Duration.ofMillis(n);switch(which){case 0:return d.toNanos();case 1:return d.toMillis();case 2:return d.getSeconds();case 3:return d.getNano();case 4:return Duration.ofMillis(0)==Duration.ofMillis(0)?4:0;case 5:Duration q=null;return q.toNanos();default:return 99;}}catch(ArithmeticException e){return 105;}catch(NullPointerException e){return 106;}}
 public static int parse(String s,int n){try{return n==0?(Boolean.parseBoolean(s)?1:0):Integer.parseInt(s);}catch(NumberFormatException e){return 107;}}
}'''
driver='''import net.minecraft.test.DurationDemo;public class DurationDriver{public static void main(String[]a){for(int i=0;i<a.length;i+=2)System.out.println(DurationDemo.run(Long.parseLong(a[i]),Integer.parseInt(a[i+1])));}}'''
driver2='''import net.minecraft.test.DurationDemo;public class ParseDriver{public static void main(String[]a){for(int i=0;i<a.length;i+=2)System.out.println(DurationDemo.parse(a[i].equals("@null")?null:a[i],Integer.parseInt(a[i+1])));}}'''
with tempfile.TemporaryDirectory(prefix='mc-duration-') as t:
 d=pathlib.Path(t);(d/'DurationDemo.java').write_text(source);(d/'DurationDriver.java').write_text(driver);(d/'ParseDriver.java').write_text(driver2);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DurationDemo.java'),str(d/'DurationDriver.java'),str(d/'ParseDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DurationDemo',str(d/'native'),'run','(JI)J','parse','(Ljava/lang/String;I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[(str(m),str(n)) for m in [0,1,-1,999,-999,1000,-1001,9223372036854,-9223372036854,9223372036854775807,-9223372036854775808] for n in range(6)]*3;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DurationDriver',*[v for p in vals for v in p]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for m,n in vals for v in ('0',m,n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 vals=[(s,str(n)) for s in ('@null','true','TRUE','false','','+12','-2147483648','2147483648','-0','+',' 1','1x') for n in (0,1)]*3;java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ParseDriver',*[v for p in vals for v in p]],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for s,n in vals for v in ('1','null' if s=='@null' else 's:'+s,n)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run([str(d/'native'),'1','s:١','1'],capture_output=True,text=True)
 if p.returncode!=2 or 'dígitos Unicode no soportados' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 198 Durations y 72 parseos Java; overflow, negativos, null y guardas Unicode')
