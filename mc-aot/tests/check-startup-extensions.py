#!/usr/bin/env python3
"""Diferencial de rutas JDK usadas en arranque, con guardas explícitas."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.util.*;import java.time.*;import java.lang.reflect.Array;
public class StartupExtensions {
 static float[] f=new float[2];static double[] d=new double[2];
 public static int run(int n){try{switch(n%27){
 case 0:HashMap<String,String> m=new HashMap<>();m.put(null,"hey");return m.get(null).length();
 case 1:HashMap<String,String> m1=new HashMap<>();m1.put("x",null);return m1.containsKey("x")?1:0;
 case 2:HashMap<String,String> m2=new HashMap<>();m2.put("x",null);return m2.putIfAbsent("x","abc")==null?m2.get("x").length():0;
 case 3:HashMap<String,String> m3=new HashMap<>();m3.put("x",null);m3.remove("x");return m3.size();
 case 4:HashMap<String,String> m4=new HashMap<>();m4.put("x","y");m4.clear();return m4.isEmpty()?4:0;
 case 5:HashMap<String,String> m5=new HashMap<>(Collections.emptyMap());return m5.size();
 case 6:ArrayDeque<String> q=new ArrayDeque<>();q.push("one");q.addLast("two");return q.pop().length()*10+q.removeLast().length();
 case 7:ArrayDeque<String> q1=new ArrayDeque<>();return q1.pollFirst()==null?7:0;
 case 8:new ArrayDeque<String>().pop();return -1;
 case 9:new ArrayDeque<String>().add(null);return -1;
 case 10:f[0]=2.5f;return (int)(f[0]*2);
 case 11:d[1]=-3.125;return (int)(d[1]*8);
 case 12:return Array.getLength(f)+Array.getLength(d);
 case 13:Array.getLength("x");return -1;
 case 14:Array.getLength(null);return -1;
 case 15:CharSequence[] cs={"abc",new StringBuilder("XY")};return cs[0].length()*10+cs[1].charAt(1);
 case 16:Object[] ar=new CharSequence[1];ar[0]=Integer.valueOf(1);return -1;
 case 17:String text="a😀b";return text.substring(1,3).length()*100+text.substring(1,3).charAt(0);
 case 18:String text2="abc";return text2.substring(0)==text2?18:0;
 case 19:"abc".substring(3,2);return -1;
 case 20:return (int)Date.from(ZonedDateTime.parse("2026-09-15T11:20:48+00:00").toInstant()).getTime();
 case 21:return (int)ZonedDateTime.parse("1969-12-31T23:59:59.999999999Z").toInstant().toEpochMilli();
 case 22:return (int)ZonedDateTime.parse("2000-02-29T14:35:49+02:30").toInstant().toEpochMilli();
 case 23:Throwable t=new IllegalStateException();t.addSuppressed(new IllegalArgumentException());return 23;
 case 24:Throwable t2=new IllegalStateException();t2.addSuppressed(t2);return -1;
 case 25:Throwable t3=new IllegalStateException();t3.addSuppressed(null);return -1;
 default:return (int)ZonedDateTime.parse("0000-01-01T00:00:00-18:00").toInstant().toEpochMilli();
 }}catch(NoSuchElementException e){return 71;}catch(NullPointerException e){return 72;}catch(ArrayStoreException e){return 73;}catch(IndexOutOfBoundsException e){return 74;}catch(IllegalArgumentException e){return 75;}}
 public static int bad(){return (int)ZonedDateTime.parse("2026-01-01T00:00:00[America/New_York]").toInstant().toEpochMilli();}
}'''
driver='''import net.minecraft.test.StartupExtensions;public class ExtDriver{public static void main(String[]a){for(String x:a)System.out.println(StartupExtensions.run(Integer.parseInt(x)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-startup-ext-') as t:
 d=pathlib.Path(t);(d/'StartupExtensions.java').write_text(src);(d/'ExtDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'StartupExtensions.java'),str(d/'ExtDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/StartupExtensions'];p=subprocess.run(base+[str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(135));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'ExtDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True)
 if a.returncode or j!=a.stdout:raise AssertionError((a.returncode,j,a.stdout,a.stderr))
 p=subprocess.run([str(d/'native'),'1'],capture_output=True,text=True)
 if p.returncode==0 or 'fuera del perfil' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 135 operaciones HashMap/ArrayDeque, arrays F/D, CharSequence, reflexión, fechas, substring y suppressed; guarda de zona nombrada')
