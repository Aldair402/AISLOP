#!/usr/bin/env python3
"""Preparación de campos F/D por bits y lectura/escritura de bytecode."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class Floats {
 static float f;static double d;
 static final float fn=-0.0f,fp=1.5f,fmin=Float.MIN_VALUE,fmax=Float.MAX_VALUE,fi=1.0f/0.0f,fnan=0.0f/0.0f;
 static final double dn=-0.0,dp=1.5,dmin=Double.MIN_VALUE,dmax=Double.MAX_VALUE,di=1.0/0.0,dnan=0.0/0.0;
 static int safe(){return 42;}static int read(){return f==0?1:0;}static void write(){f=2.0f;}
}
'''
driver='''import java.lang.reflect.*;
public class FloatBitsDriver {public static void main(String[] names)throws Exception {Class<?> c=Class.forName("net.minecraft.test.Floats");for(String s:names){Field f=c.getDeclaredField(s);f.setAccessible(true);if(f.getType()==float.class)System.out.printf("fbits:%08x%n",Float.floatToRawIntBits(f.getFloat(null)));else System.out.printf("dbits:%016x%n",Double.doubleToRawLongBits(f.getDouble(null)));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-float-prep-') as t:
 d=pathlib.Path(t);(d/'Floats.java').write_text(source);(d/'FloatBitsDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'Floats.java'),str(d/'FloatBitsDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 names=['f','d','fn','fp','fmin','fmax','fi','fnan','dn','dp','dmin','dmax','di','dnan'];types=['F','D']+['F']*6+['D']*6
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Floats',str(d/'native')]
 for name,desc in zip(names,types):cmd+=['@'+name,desc]
 cmd+=['safe','()I'];p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'FloatBitsDriver',*names],capture_output=True,text=True,check=True).stdout.splitlines()
 native=subprocess.run([str(d/'native'),*map(str,range(len(names))),str(len(names))],capture_output=True,text=True,check=True).stdout.splitlines()
 if native!=java+['42']:raise AssertionError((java,native))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/Floats',str(d/'rw'),'read','()I','write','()V'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 result=subprocess.run([str(d/'rw'),'0','1','0'],capture_output=True,text=True,check=True).stdout
 if result!='1\nOK\n0\n':raise AssertionError(result)
 print(f'OK: {len(names)} campos float/double preparados por bits; lectura y escritura Java verificadas')
