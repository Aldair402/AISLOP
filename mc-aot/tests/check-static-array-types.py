#!/usr/bin/env python3
"""Campos estáticos de arrays primitivos: carga, escritura y alias entre clases."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class ArrayState {
 static boolean[] z={true,false};static byte[] b={-128,127};static char[] c={0,65535};
 static short[] s={-32768,32767};static int[] i={Integer.MIN_VALUE,Integer.MAX_VALUE};static long[] j={Long.MIN_VALUE,Long.MAX_VALUE};
 public static void bind(){ArrayAlias.z=z;ArrayAlias.b=b;ArrayAlias.c=c;ArrayAlias.s=s;ArrayAlias.i=i;ArrayAlias.j=j;}
 public static int apply(int n){ArrayAlias.z[0]=(n&1)!=0;ArrayAlias.b[0]=(byte)n;ArrayAlias.c[0]=(char)n;ArrayAlias.s[0]=(short)n;ArrayAlias.i[0]=n;ArrayAlias.j[0]=n;return (z[0]?1:0)+b[0]+c[0]+s[0]+i[0]+(int)j[0];}
 public static int check(){return (ArrayAlias.z[0]?1:0)+ArrayAlias.b[0]+ArrayAlias.c[0]+ArrayAlias.s[0]+ArrayAlias.i[0]+(int)ArrayAlias.j[0];}
}
class ArrayAlias {static boolean[] z;static byte[] b;static char[] c;static short[] s;static int[] i;static long[] j;}
'''
driver='''import net.minecraft.test.ArrayState;
public class ArrayStateDriver {public static void main(String[] a){ArrayState.bind();System.out.println("OK");for(String s:a){System.out.println(ArrayState.apply(Integer.parseInt(s)));System.out.println(ArrayState.check());}}}'''
with tempfile.TemporaryDirectory(prefix='mc-static-array-types-') as t:
 d=pathlib.Path(t);(d/'ArrayState.java').write_text(source);(d/'ArrayStateDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ArrayState.java'),str(d/'ArrayStateDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 specs=[('bind','()V'),('apply','(I)I'),('check','()I')]+[('@'+name,'['+ty) for name,ty in [('z','Z'),('b','B'),('c','C'),('s','S'),('i','I'),('j','J')]]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ArrayState',str(d/'native')]
 for n,desc in specs:cmd.extend([n,desc])
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(551);values=[-2147483648,-65537,-32769,-129,-1,0,1,127,128,32767,65535,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(100)]
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ArrayStateDriver',*map(str,values)],capture_output=True,text=True,check=True).stdout.splitlines()
 args=['0'];
 for n in values:args+=['1',str(n),'2']
 native=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout.splitlines()
 if java!=native:raise AssertionError(next(((i,a,b) for i,(a,b) in enumerate(zip(java,native)) if a!=b),('longitud',len(java),len(native))))
 diag=subprocess.run([str(d/'native'),'3','4','5','6','7','8'],capture_output=True,text=True,check=True).stdout.splitlines()
 want=['[1,0]','[-128,127]','[0,65535]','[-32768,32767]','[-2147483648,2147483647]','[-9223372036854775808,9223372036854775807]']
 if diag!=want:raise AssertionError((diag,want))
 print(f'OK: {len(java)} operaciones Java; seis tipos de arrays estáticos, alias y estrechamiento; 6 formatos de diagnóstico')
