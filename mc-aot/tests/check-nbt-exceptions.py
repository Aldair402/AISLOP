#!/usr/bin/env python3
"""Jerarquía y constructor real NbtException; validación conservadora de clases propias."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';minecraft=root.parent/'downloads/server-26.3-inner.jar'
source='''package net.minecraft.test;
import net.minecraft.nbt.NbtException;
import net.minecraft.nbt.ReportedNbtException;
public class NbtFixture {
 public static int route(int n) {
  try {
   if(n==0)throw new NbtException("nbt");
   if(n==1)throw new NestedNbt("nested");
   if(n==2)throw new ArithmeticException();
   return n;
  } catch(NestedNbt e){return 11;}catch(NbtException e){return 12;}
    catch(ReportedNbtException e){return 13;}catch(RuntimeException e){return 14;}
 }
 public static int identity(int n) {
  try {if(n==0)throw new NestedNbt("id");return n;}
  catch(NbtException e){try{throw e;}catch(NestedNbt f){return e==f?31:32;}catch(NbtException f){return 33;}}
 }
 public static int rejectField(int n){throw new FieldException("x");}
 public static int rejectInit(int n){throw new InitException("x");}
 public static int rejectBody(int n){throw new BodyException("x");}
}
class NestedNbt extends NbtException {NestedNbt(String s){super(s);}}
class FieldException extends RuntimeException {int value;FieldException(String s){super(s);}}
class InitException extends RuntimeException {static int value=1;InitException(String s){super(s);}}
class BodyException extends RuntimeException {BodyException(String s){super(s);touch();}static void touch(){}}
'''
driver='''import java.io.*;import net.minecraft.test.NbtFixture;
public class NbtReference {public static void main(String[] args)throws Exception {var in=new BufferedReader(new InputStreamReader(System.in));for(String s;(s=in.readLine())!=null;){String[] p=s.split(" ");try {int n=Integer.parseInt(p[1]);System.out.println(p[0].equals("route")?NbtFixture.route(n):NbtFixture.identity(n));}catch(Throwable e){System.out.println("EX:"+e.getClass().getSimpleName());}}}}'''
with tempfile.TemporaryDirectory(prefix='mc-nbt-exceptions-') as tmp:
 d=pathlib.Path(tmp);(d/'NbtFixture.java').write_text(source);(d/'NbtReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(minecraft),'-d',str(d),str(d/'NbtFixture.java'),str(d/'NbtReference.java')],check=True)
 with zipfile.ZipFile(minecraft) as z:
  for name in ['net/minecraft/nbt/NbtException.class','net/minecraft/nbt/ReportedNbtException.class','net/minecraft/ReportedException.class']:
   p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 for name in ['route','identity']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'test.jar'),'net/minecraft/test/NbtFixture',name,'(I)I',str(d/name)],capture_output=True,text=True)
  if p.returncode:raise RuntimeError((name,p.stderr))
 cases=[(name,n) for name in ['route','identity'] for n in range(-3,10)]
 result=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),str(minecraft)]),'NbtReference'],input=''.join(f'{n} {x}\n' for n,x in cases),capture_output=True,text=True,check=True).stdout.splitlines()
 if len(result)!=len(cases):raise AssertionError(('results',result))
 for (name,n),expected in zip(cases,result):
  got=subprocess.run([str(d/name),str(n)],capture_output=True,text=True)
  if got.returncode or got.stdout.strip()!=expected:raise AssertionError((name,n,expected,got.stdout,got.stderr))
 for name,err in [('rejectField','con estado o inicializador'),('rejectInit','con estado o inicializador'),('rejectBody','constructor de excepción no trivial')]:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'test.jar'),'net/minecraft/test/NbtFixture',name,'(I)I',str(d/name)],capture_output=True,text=True)
  if p.returncode==0 or err not in p.stderr or (d/name).exists():raise AssertionError((name,p.stderr))
 print(f'OK: {len(cases)} comparaciones Java con NbtException real, subclase, orden de catch y relanzamiento; 3 constructores/clases no triviales rechazados')
