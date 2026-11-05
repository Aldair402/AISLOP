#!/usr/bin/env python3
"""Excepciones capturadas durante <clinit> y operaciones de un static-demo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
fixture='''package net.minecraft.test;
public class InitExceptions {
 public static int value;
 static {try{value=9/zero();}catch(ArithmeticException e){value=27;}}
 static int zero(){return 0;}
 public static int get(){return value;}
 public static int step(int n){try{value+=10/n;}catch(ArithmeticException e){value+=4;}return value;}
}'''
driver='''import net.minecraft.test.InitExceptions;
public class InitExceptionsReference {public static void main(String[] args){System.out.println(InitExceptions.get());for(String a:args)System.out.println(InitExceptions.step(Integer.parseInt(a)));System.out.println(InitExceptions.get());}}'''
with tempfile.TemporaryDirectory(prefix='mc-init-exceptions-') as t:
 d=pathlib.Path(t);(d/'InitExceptions.java').write_text(fixture);(d/'InitExceptionsReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InitExceptions.java'),str(d/'InitExceptionsReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','static-demo',str(d/'test.jar'),'net/minecraft/test/InitExceptions',str(d/'demo'),'get','()I','step','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 args=['0','2','-2','0','5','1','0'];commands=['0'];
 for x in args:commands.extend(['1',x])
 commands+=['0']
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'InitExceptionsReference',*args],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'demo'),*commands],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 print(f'OK: <clinit> con excepción capturada y {len(args)+2} operaciones con estado coinciden con Java 25')
