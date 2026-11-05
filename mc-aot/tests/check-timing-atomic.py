#!/usr/bin/env python3
"""AtomicLong monohilo y Duration entre Instants exactos con fracciones negativas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.time.*;import java.util.concurrent.atomic.AtomicLong;public class TimeAtomicDemo{public static long run(int n){AtomicLong a=new AtomicLong(Long.MAX_VALUE);switch(n%8){case 0:return a.getAndIncrement();case 1:return a.incrementAndGet();case 2:return a.compareAndSet(Long.MAX_VALUE,-7)?a.get():0;case 3:return a.getAndSet(-1);case 4:Instant x=ZonedDateTime.parse("1969-12-31T23:59:59.999999999Z").toInstant();Instant y=ZonedDateTime.parse("1970-01-01T00:00:00Z").toInstant();return Duration.between(y,x).toMillis();case 5:Instant z=ZonedDateTime.parse("1970-01-01T00:00:00.001000001Z").toInstant();Instant o=ZonedDateTime.parse("1970-01-01T00:00:00Z").toInstant();return Duration.between(z,o).toMillis();case 6:Instant p=ZonedDateTime.parse("1970-01-01T00:00:00Z").toInstant();return Duration.between(p,p)==Duration.ofMillis(0)?6:0;default:a.set(-3);return a.get();}}}'''
driver='''import net.minecraft.test.TimeAtomicDemo;public class AtomicDriver{public static void main(String[]a){for(String x:a)System.out.println(TimeAtomicDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-time-atomic-') as t:
 d=pathlib.Path(t);(d/'TimeAtomicDemo.java').write_text(src);(d/'AtomicDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'TimeAtomicDemo.java'),str(d/'AtomicDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/TimeAtomicDemo',str(d/'native'),'run','(I)J'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(80));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'AtomicDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 print('OK: 80 operaciones AtomicLong monohilo y Duration entre Instants, incluidas fracciones negativas')
