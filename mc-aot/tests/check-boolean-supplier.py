#!/usr/bin/env python3
"""BooleanSupplier con lambda y receptor concreto comparados con Java."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.function.BooleanSupplier;
public class BooleanSupplierProbe {
 static int count;static boolean next(){return (++count&1)!=0;}
 static final class Const implements BooleanSupplier {final int value;Const(int x){value=x;}public boolean getAsBoolean(){return (value&1)!=0;}}
 public static int run(int n){try{BooleanSupplier a=BooleanSupplierProbe::next;BooleanSupplier b=()->n>3;BooleanSupplier c=new Const(n);BooleanSupplier d=null;return (a.getAsBoolean()?1:0)+(a.getAsBoolean()?2:0)+(b.getAsBoolean()?4:0)+(c.getAsBoolean()?8:0)+(n==42&&d.getAsBoolean()?16:0);}catch(NullPointerException e){return 100;}}
}'''
driver='''import net.minecraft.test.BooleanSupplierProbe;public class BooleanSupplierDriver{public static void main(String[]a){for(String n:a)System.out.println(BooleanSupplierProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-boolsupplier-') as tmp:
 d=pathlib.Path(tmp);(d/'BooleanSupplierProbe.java').write_text(source);(d/'BooleanSupplierDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'BooleanSupplierProbe.java'),str(d/'BooleanSupplierDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/BooleanSupplierProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-20,61));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'BooleanSupplierDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 print(f'OK: {len(vals)} resultados BooleanSupplier con lambdas con/sin capturas, receptor concreto, efectos y null frente a Java')
