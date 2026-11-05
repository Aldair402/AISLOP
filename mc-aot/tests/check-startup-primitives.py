#!/usr/bin/env python3
"""JDK mínimo para arranque: Optional, UUID, fecha, regex fijo y records."""
import os,pathlib,subprocess,tempfile,time
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src=r'''package net.minecraft.test;import java.util.*;import java.util.regex.*;import java.util.function.*;import java.io.Serializable;
record Pair(int x,long y){}
class SerialThing implements Serializable {} class PlainThing {}
public class StartupDemo {
 static final String PAT="%(?:(\\d+)\\$)?([A-Za-z%]|$)";
 public static int run(int n){try{switch(n%14){case 0:return Optional.of("x").get().length();case 1:return Optional.empty().isEmpty()?2:0;case 2:return Optional.<String>ofNullable(null).orElse("abc").length();case 3:Optional.of(null);return -1;case 4:Optional.empty().get();return -1;case 5:return new Pair(n,19L).x();case 6:return (int)new Pair(n,19L).y();case 7:return Pattern.compile(PAT).pattern()==PAT?7:0;case 8:return ((Function<Pattern,String>)Pattern::pattern).apply(Pattern.compile(PAT)).length();case 9:return "a-b-c".replaceAll("-","").length();case 10:return "abc".replaceAll("-","")=="abc"?10:0;case 11:return ((Object)new SerialThing()) instanceof Serializable?11:0;case 12:return ((Object)Optional.empty()) instanceof Serializable?0:12;default:return Character.toString(0x1f600).length();}}catch(NullPointerException e){return 77;}catch(NoSuchElementException e){return 88;}}
 public static long date(long n){Date d=new Date(n);d.setTime(d.getTime()+1);return d.getTime();}
 public static long now(){return new Date().getTime();}
 public static int uuid(){UUID u=UUID.randomUUID();String s=u.toString();return u.version()*1000+u.variant()*100+s.length()*2+s.replaceAll("-","").length();}
 public static int badPattern(){return Pattern.compile("(").pattern().length();}
 public static int badReplace(){return "abc".replaceAll(".","").length();}
 public static int badRecord(){return new Pair(1,2).toString().length();}
}'''
driver='''import net.minecraft.test.StartupDemo;public class StartupDriver{public static void main(String[]a){for(String x:a)System.out.println(StartupDemo.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-startup-') as t:
 d=pathlib.Path(t);(d/'StartupDemo.java').write_text(src);(d/'StartupDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StartupDemo.java'),str(d/'StartupDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/StartupDemo']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I','date','(J)J','now','()J','uuid','()I','badPattern','()I','badReplace','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(140));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'StartupDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[x for n in vals for x in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if j!=a:raise AssertionError((j,a))
 dates=[-9223372036854775808,-1,0,1,2147483647,9223372036854775806];a=subprocess.run([str(d/'native'),*[x for n in dates for x in ('1',str(n))]],capture_output=True,text=True,check=True).stdout.splitlines();assert list(map(int,a))==[n+1 for n in dates]
 before=int(time.time()*1000);p=subprocess.run([str(d/'native'),'2',*(['3']*80)],capture_output=True,text=True,check=True);after=int(time.time()*1000);lines=list(map(int,p.stdout.splitlines()));assert before-2000<=lines[0]<=after+2000 and all(x==4304 for x in lines[1:]),lines
 for mode,err in [('4','Pattern.compile'),('5','String.replaceAll')]:
  p=subprocess.run([str(d/'native'),mode],capture_output=True,text=True);assert p.returncode and err in p.stderr,(p.returncode,p.stderr)
 p=subprocess.run(base+[str(d/'bad'),'badRecord','()I'],capture_output=True,text=True);assert p.returncode and ('bootstrap' in p.stderr or 'invokedynamic' in p.stderr),p.stderr
 print('OK: 140 resultados Java Optional/regex/records/Serializable; 6 fechas, reloj y 80 UUID v4; guardas')
