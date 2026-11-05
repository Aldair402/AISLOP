#!/usr/bin/env python3
"""Opt-in de compilación equiparable a Java -XX:-FlightRecorder."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import jdk.jfr.FlightRecorder;public class JfrDemo{public static int run(int n){if(Runtime.class.getModule().getLayer().findModule("jdk.jfr").isPresent()&&FlightRecorder.isAvailable())return new java.math.BigInteger("10").intValue();return n+7;}}'''
driver='''import net.minecraft.test.JfrDemo;public class JfrDriver{public static void main(String[]a){for(String x:a)System.out.println(JfrDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-jfr-profile-') as t:
 d=pathlib.Path(t);(d/'JfrDemo.java').write_text(src);(d/'JfrDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'JfrDemo.java'),str(d/'JfrDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/JfrDemo'];env=os.environ.copy();env.pop('MC_AOT_DISABLE_JFR',None)
 p=subprocess.run(base+[str(d/'disabled'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode==0:raise AssertionError('JFR activo no debe compilarse como desactivado')
 env['MC_AOT_DISABLE_JFR']='1';p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True,env=env)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(70));j=subprocess.run([str(jdk/'java'),'-XX:-FlightRecorder','-cp',str(d),'JfrDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 70 operaciones con JFR explícitamente desactivado; sin perfil se rechaza')
