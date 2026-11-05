#!/usr/bin/env python3
"""Método real de Minecraft que construye y lanza IllegalArgumentException."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parent.parent;jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root/'downloads/server-26.3-inner.jar'
source='''import java.io.*;import java.lang.reflect.*;
public class NeighborReference { public static void main(String[] a)throws Exception{var m=Class.forName("net.minecraft.world.level.lighting.LayerLightSectionStorage$SectionState").getDeclaredMethod("neighborCount",byte.class,int.class);m.setAccessible(true);var in=new BufferedReader(new InputStreamReader(System.in));for(String s;(s=in.readLine())!=null;){var x=s.split(",");try{System.out.println(m.invoke(null,(byte)Integer.parseInt(x[0]),Integer.parseInt(x[1])));}catch(InvocationTargetException e){System.out.println("EX:"+e.getCause().getClass().getSimpleName());}}}}
'''
with tempfile.TemporaryDirectory(prefix='mc-neighbor-exception-') as t:
 d=pathlib.Path(t);(d/'NeighborReference.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-cp',str(jar),'-d',str(d),str(d/'NeighborReference.java')],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','compile',str(jar),'net/minecraft/world/level/lighting/LayerLightSectionStorage$SectionState','neighborCount','(BI)B',str(d/'neighbor')],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 cases=[(b,n) for b in range(-128,128) for n in (-2147483648,-1,0,1,25,26,27,2147483647)]
 inp=''.join(f'{b},{n}\n' for b,n in cases)
 ref=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join((str(d),str(jar))),'NeighborReference'],input=inp,capture_output=True,text=True,check=True).stdout.splitlines()
 if len(ref)!=len(cases):raise AssertionError((len(ref),len(cases)))
 for (b,n),expected in zip(cases,ref):
  got=subprocess.run([str(d/'neighbor'),str(b),str(n)],capture_output=True,text=True)
  if expected.startswith('EX:'):
   if got.returncode!=2 or expected[3:] not in got.stderr:raise AssertionError((b,n,expected,got.returncode,got.stdout,got.stderr))
  elif got.returncode or got.stdout.strip()!=expected:raise AssertionError((b,n,expected,got.returncode,got.stdout,got.stderr))
 print(f'OK: {len(cases)} casos de SectionState.neighborCount(byte,int) coinciden con Java 25 en valor o categoría de IllegalArgumentException; mensaje y stack trace no comparados')
