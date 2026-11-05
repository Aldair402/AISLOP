#!/usr/bin/env python3
"""StringConcatFactory: recetas reales, constantes escapadas y valores primitivos."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;public class ConcatDemo {
 public static String run(String s,int n,long l,boolean b,char c){return "A\u0001/"+s+"/"+n+":"+l+":"+b+":"+c+"/\u0002Z";}
 public static int identity(String s){return (""+s)==s?1:0;}
 public static int other(Object o){return ("x"+o).length();}
 public static int lambda(String n){return ((java.util.function.Function<String,String>)String::toUpperCase).apply(n).length();}
}'''
# Java procesa los escapes Unicode antes de lexear, incluso dentro de strings.
driver='''import net.minecraft.test.ConcatDemo;public class ConcatDriver{public static void main(String[]a){for(int i=0;i<a.length;i+=5){String s=a[i].equals("@null")?null:a[i];System.out.println(ConcatDemo.run(s,Integer.parseInt(a[i+1]),Long.parseLong(a[i+2]),a[i+3].equals("1"),(char)Integer.parseInt(a[i+4])));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-indy-concat-') as t:
 d=pathlib.Path(t);(d/'ConcatDemo.java').write_text(source);(d/'ConcatDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ConcatDemo.java'),str(d/'ConcatDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ConcatDemo']
 p=subprocess.run(base+[str(d/'native'),'run','(Ljava/lang/String;IJZC)Ljava/lang/String;','identity','(Ljava/lang/String;)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=[(x,str(n),str(l),str(b),str(c)) for x in ('@null','hola','á😀') for n,l,b,c in [(-2147483648,-9223372036854775808,0,65),(2147483647,9223372036854775807,1,233),(0,0,1,32)]]*5
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ConcatDriver',*[v for seq in vals for v in seq]],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*[v for x,n,l,b,c in vals for v in ('0','null' if x=='@null' else 's:'+x,n,l,b,c)]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 native=subprocess.run([str(d/'native'),'1','s:abc'],capture_output=True,text=True,check=True).stdout
 if native!='0\n':raise AssertionError(native)
 p=subprocess.run(base+[str(d/'lambda'),'lambda','(Ljava/lang/String;)I'],capture_output=True,text=True)
 if p.returncode==0 or 'lambda método JDK no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print(f'OK: {len(vals)} concatenaciones Java StringConcatFactory con Unicode, constantes, boolean/char/int/long y null; referencia a método virtual rechazada')
