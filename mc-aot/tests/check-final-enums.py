#!/usr/bin/env python3
"""Enums finales directos: inicialización, ordinal/name, arrays covariantes y clone."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class EnumDemo {
 enum Mode { ALPHA(3), BETA(7), GAMMA(11); final int score;Mode(int x){score=x;}int score(){return score;} }
 static Object[] alias(Object[] a){return a;}
 public static int run(int n){try{switch(n){
 case 0:return Mode.ALPHA.ordinal()*100+Mode.BETA.ordinal()*10+Mode.GAMMA.ordinal();
 case 1:return Mode.ALPHA.name().equals("ALPHA")&&Mode.BETA.name()=="BETA"?1:0;
 case 2:return Mode.GAMMA.score()+Mode.BETA.score()+Mode.ALPHA.score();
 case 3:Mode[] x=Mode.values();Mode[] y=Mode.values();x[0]=Mode.BETA;return (x!=y?1:0)+(y[0]==Mode.ALPHA?2:0)+(y.length==3?4:0);
 case 4:Object[] o=alias(Mode.values());o[0]="wrong";return -1;
 case 5:Object[] p=alias(Mode.values());p[2]=null;return p[2]==null?5:0;
 case 6:Mode[] v=(Mode[])(Object)Mode.values();return v[1].ordinal();
 case 7:Mode[] bad=(Mode[])(Object)new String[0];return -1;
 case 8:Mode nil=null;return nil.ordinal();
 default:return 99;
 }}catch(ArrayStoreException e){return 101;}catch(ClassCastException e){return 102;}catch(NullPointerException e){return 103;}}
}'''
bad='''package net.minecraft.test;public class EnumRejected {enum E {X{int f(){return 1;}},Y{int f(){return 2;}};abstract int f();}public static int run(){E[] a=E.values();return a[0].f()*1000+a[1].f()*100+a[1].ordinal()*10+a[0].name().length();}}'''
bad_driver='''import net.minecraft.test.EnumRejected;public class BadEnumDriver{public static void main(String[] a){System.out.println(EnumRejected.run());}}'''
driver='''import net.minecraft.test.EnumDemo;public class EnumDriver{public static void main(String[] a){for(String s:a)System.out.println(EnumDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-enum-') as t:
 d=pathlib.Path(t);(d/'EnumDemo.java').write_text(source);(d/'EnumRejected.java').write_text(bad);(d/'EnumDriver.java').write_text(driver);(d/'BadEnumDriver.java').write_text(bad_driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'EnumDemo.java'),str(d/'EnumRejected.java'),str(d/'EnumDriver.java'),str(d/'BadEnumDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar')]
 p=subprocess.run(base+['net/minecraft/test/EnumDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[str(n) for n in list(range(9))*10+[-1,9]];java=subprocess.run([str(jdk/'java'),'-cp',str(d),'EnumDriver',*vals],capture_output=True,text=True,check=True).stdout;native=subprocess.run([str(d/'native'),*[v for x in vals for v in ('0',x)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run(base+['net/minecraft/test/EnumRejected',str(d/'bad'),'run','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 j=subprocess.run([str(jdk/'java'),'-cp',str(d),'BadEnumDriver'],capture_output=True,text=True,check=True).stdout
 n=subprocess.run([str(d/'bad'),'0'],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(vals)} operaciones Java de enum final y enum con subclases por constante, despacho, values/clone y ordinal')
