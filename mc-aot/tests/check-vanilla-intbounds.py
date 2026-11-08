#!/usr/bin/env python3
"""Class-demo: String en UTF-16, y BlockUtil.IntBounds completo contra Java."""
import os, pathlib, random, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
jar=root.parent/'downloads/server-26.3-inner.jar'
compiler=root/'target/debug/mc-aot'
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
def run(args, **kwargs):
    return subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=180,**kwargs)
source=r'''package net.minecraft.test;
public class Texts {
 public Texts() {}
 public String empty() { return ""; }
 public String nul() { return null; }
 public String unicode() { return "A\u0000\ud800\ud83d\ude00Z"; }
}'''
driver=r'''import java.lang.reflect.*;
public class Oracle {
 static void print(String s){if(s==null){System.out.println("s:null");return;}
   System.out.print("s16:");for(int i=0;i<s.length();i++)System.out.printf("%04x",(int)s.charAt(i));System.out.println();}
 public static void main(String[] a) throws Exception {
   if(a[0].equals("text")){net.minecraft.test.Texts o=new net.minecraft.test.Texts();System.out.println("OK");print(o.empty());print(o.nul());print(o.unicode());return;}
   Class<?> c=Class.forName("net.minecraft.util.BlockUtil$IntBounds");Constructor<?> k=c.getConstructor(int.class,int.class);
   for(int i=1;i<a.length;i+=2){Object o=k.newInstance(Integer.parseInt(a[i]),Integer.parseInt(a[i+1]));System.out.println("OK");
    System.out.println(c.getField("min").getInt(o));System.out.println(c.getField("max").getInt(o));print((String)c.getDeclaredMethod("toString").invoke(o));}
 }
}'''
with tempfile.TemporaryDirectory(prefix='mc-intbounds-') as tmp:
 d=pathlib.Path(tmp); (d/'Texts.java').write_text(source); (d/'Oracle.java').write_text(driver)
 c=run([jdk/'javac','-d',d,d/'Texts.java',d/'Oracle.java']);assert c.returncode==0,c.stderr
 fixture=d/'fixture.jar';c=run([jdk/'jar','cf',fixture,'-C',d,'net']);assert c.returncode==0,c.stderr
 env=dict(os.environ,PATH='/nonexistent')
 for label,srcjar,clazz,steps in [('text',fixture,'net/minecraft/test/Texts',['new','--','empty','--','nul','--','unicode'])]:
  binary=d/'texts';c=run([compiler,'class-demo',srcjar,clazz,binary]);assert c.returncode==0,c.stderr
  j=run([jdk/'java','-cp',d,'Oracle',label]);n=run([binary,*steps],env=env)
  assert j.returncode==n.returncode==0 and j.stdout==n.stdout,(j.stderr,n.stderr,j.stdout,n.stdout)
 binary=d/'bounds';c=run([compiler,'class-demo',jar,'net/minecraft/util/BlockUtil$IntBounds',binary]);assert c.returncode==0,c.stderr
 rng=random.Random(1126);pairs=[(0,0),(-2147483648,2147483647),(-1,1)]+[(rng.randint(-2147483648,2147483647),rng.randint(-2147483648,2147483647)) for _ in range(97)]
 j=run([jdk/'java','-cp',f'{d}{os.pathsep}{jar}','Oracle','bounds',*[str(x) for pair in pairs for x in pair]])
 steps=[]
 for a,b in pairs:
  if steps:steps+=['--']
  steps+=['new',str(a),str(b),'--','read','min','--','read','max','--','toString']
 n=run([binary,*steps],env=env)
 assert j.returncode==n.returncode==0,(j.stderr,n.stderr)
 assert j.stdout==n.stdout,(j.stdout,n.stdout)
 print('OK: BlockUtil$IntBounds completo, 100 pares contra Java 25; String vacío, null y UTF-16 con sustituto aislado; nativo sin JVM')
