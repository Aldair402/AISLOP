#!/usr/bin/env python3
"""ThreadLocal.withInitial monohilo: inicialización perezosa y remove/set."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.function.Supplier;
public class SuppliedDemo{static int calls;static ThreadLocal<String> t=ThreadLocal.withInitial(()->{calls++;return "hi";});static ThreadLocal<String> nil=ThreadLocal.withInitial(()->{calls++;return null;});static ThreadLocal<String> bad=ThreadLocal.withInitial(()->{calls++;throw new IllegalArgumentException();});
 public static int run(int n){try{switch(n%11){case 0:return t.get().length()+calls*10;case 1:return t.get().length()+calls*10;case 2:t.set(null);return calls;case 3:return t.get()==null?calls:99;case 4:t.remove();return calls;case 5:return nil.get()==null?calls:99;case 6:return nil.get()==null?calls:99;case 7:nil.remove();return calls;case 8:bad.get();return -1;case 9:ThreadLocal.withInitial((Supplier<Object>)null);return -1;default:return calls;}}catch(IllegalArgumentException e){return 70+calls;}catch(NullPointerException e){return 80+calls;}}
}'''
driver='''import net.minecraft.test.SuppliedDemo;public class SuppliedDriver{public static void main(String[]a){for(String s:a)System.out.println(SuppliedDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-tl-supplier-') as t:
 d=pathlib.Path(t);(d/'SuppliedDemo.java').write_text(src);(d/'SuppliedDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SuppliedDemo.java'),str(d/'SuppliedDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SuppliedDemo',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(110));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'SuppliedDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[x for n in vals for x in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 print('OK: 110 operaciones ThreadLocal.withInitial, null, remove, reintento y excepción')
