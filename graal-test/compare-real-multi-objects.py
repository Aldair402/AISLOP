#!/usr/bin/env python3
"""Objetos y mutaciones en tres clases reales, a través de un adaptador sintético."""
import os,pathlib,random,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3-inner.jar'
source='''package net.minecraft.test;
import net.minecraft.commands.arguments.selector.options.SetOnceOptionState;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.server.players.SleepStatus;
public class RealObjects {
 static SetOnceOptionState option=new SetOnceOptionState();
 static CommandResponseTracker<Object> tracker=CommandResponseTracker.create();
 static SleepStatus sleep=new SleepStatus();
 public static int parse(){return option.canParse()?1:0;}
 public static void mark(){option.markParsed();}
 public static void reset(){option=new SetOnceOptionState();tracker=CommandResponseTracker.create();sleep=new SleepStatus();}
 public static int add(String text,int n){tracker.track(text,n);return tracker.totalValue();}
 public static int sum(){return tracker.totalValue();}
 public static int sleeping(){sleep.removeAllSleepers();return sleep.amountSleeping();}
}'''
driver='''import net.minecraft.test.RealObjects;public class RealObjectsDriver {public static void main(String[] a){System.out.println(RealObjects.parse());RealObjects.mark();System.out.println("OK");System.out.println(RealObjects.parse());for(String s:a){System.out.println(RealObjects.add("abc",Integer.parseInt(s)));System.out.println(RealObjects.sum());}System.out.println(RealObjects.sleeping());RealObjects.reset();System.out.println("OK");System.out.println(RealObjects.parse());System.out.println(RealObjects.sum());}}'''
with tempfile.TemporaryDirectory(prefix='mc-real-objects-') as t:
 d=pathlib.Path(t);(d/'RealObjects.java').write_text(source);(d/'RealObjectsDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(jar),'-d',str(d),str(d/'RealObjects.java'),str(d/'RealObjectsDriver.java')],check=True)
 names=['net/minecraft/commands/arguments/selector/options/SetOnceOptionState','net/minecraft/server/commands/CommandResponseTracker','net/minecraft/server/players/SleepStatus']
 with zipfile.ZipFile(jar) as z:
  for name in names:
   f=d/(name+'.class');f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(name+'.class'))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RealObjects',str(d/'native'),'parse','()I','mark','()V','reset','()V','add','(Ljava/lang/String;I)I','sum','()I','sleeping','()I']
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(123);vals=[-2147483648,-1,0,1,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(100)]
 java=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),str(jar)]),'RealObjectsDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
 args=['0','1','0']
 for v in vals:args+=['3','s:abc',str(v),'4']
 args+=['5','2','0','4']
 native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java[:400],native[:400]))
 print(f'OK: {3+2*len(vals)+4} operaciones en SetOnceOptionState, CommandResponseTracker y SleepStatus reales coinciden con Java; no son clases completas')
