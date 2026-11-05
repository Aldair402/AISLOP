#!/usr/bin/env python3
"""Siete TimeUnit: identidad, ordinal y conversión exacta con saturación."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.concurrent.TimeUnit;public class TimeUnitProbe{
 static TimeUnit unit(int n){switch(n){case 0:return TimeUnit.NANOSECONDS;case 1:return TimeUnit.MICROSECONDS;case 2:return TimeUnit.MILLISECONDS;case 3:return TimeUnit.SECONDS;case 4:return TimeUnit.MINUTES;case 5:return TimeUnit.HOURS;default:return TimeUnit.DAYS;}}
 static long val(int n){switch(n){case 0:return 0L;case 1:return 1L;case 2:return -1L;case 3:return Long.MAX_VALUE;case 4:return Long.MIN_VALUE;case 5:return 9223372036854L;case 6:return -9223372036854L;case 7:return 1001L;case 8:return -1001L;case 9:return 999999999L;default:return -999999999L;}}
 public static long run(int n){int a=n%7,b=(n/7)%7;long v=val(n/49);return unit(b).convert(v,unit(a));}
 public static long to(int n){int a=n%7,b=(n/7)%7;long v=val(n/49);TimeUnit u=unit(a);switch(b){case 0:return u.toNanos(v);case 1:return u.toMicros(v);case 2:return u.toMillis(v);case 3:return u.toSeconds(v);case 4:return u.toMinutes(v);case 5:return u.toHours(v);default:return u.toDays(v);}}
 public static int info(int n){TimeUnit a=unit(n%7);return a.ordinal()*100+a.name().length()+(a==unit(n%7)?10:0);}
 public static int nullCase(int n){try{return (int)TimeUnit.SECONDS.convert(2,null);}catch(NullPointerException e){return 8;}}
}'''
driver='''import net.minecraft.test.TimeUnitProbe;public class Driver{public static void main(String[]a){for(String n:a){int x=Integer.parseInt(n);System.out.println(TimeUnitProbe.run(x));System.out.println(TimeUnitProbe.to(x));System.out.println(TimeUnitProbe.info(x));System.out.println(TimeUnitProbe.nullCase(x));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-timeunit-') as t:
 d=pathlib.Path(t);(d/'TimeUnitProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'TimeUnitProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 names=('run','to','info','nullCase')
 for m in names:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/TimeUnitProbe',str(d/m),m,'(I)J' if m in ('run','to') else '(I)I'],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError((m,p.stderr))
 seq=list(range(7*7*11));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout.splitlines();outs=[subprocess.run([str(d/m),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout.splitlines() for m in names];native=[v for pair in zip(*outs) for v in pair]
 if j!=native:raise AssertionError([(i,a,b) for i,(a,b) in enumerate(zip(j,native)) if a!=b][:10])
 print(f'OK: {len(j)} resultados TimeUnit conversiones, saturación, identidad, nombres y null frente a Java 25')
