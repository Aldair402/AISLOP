#!/usr/bin/env python3
"""Construye .class JVM válido para formas de pila pop2/dup2/swap y compara con Java."""
import os,pathlib,struct,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
u2=lambda n:struct.pack('>H',n);u4=lambda n:struct.pack('>I',n)
pool=[]
def utf(s):
 b=s.encode('utf8');pool.append(b'\x01'+u2(len(b))+b);return len(pool)
def cl(i):pool.append(b'\x07'+u2(i));return len(pool)
this=cl(utf('net/minecraft/test/StackFixture'));parent=cl(utf('java/lang/Object'));code_name=utf('Code')
methods=[('dupPair','(II)I',4,2,bytes([0x1a,0x1b,0x5c,0x60,0x60,0x60,0xac])),
 ('popPair','(II)I',2,2,bytes([0x1a,0x1b,0x58,0x04,0xac])),
 ('popLong','(J)I',2,2,bytes([0x1e,0x58,0x04,0xac])),
 ('dupLong','(J)J',4,2,bytes([0x1e,0x5c,0x61,0xad])),
 ('intSwap','(II)I',2,2,bytes([0x1a,0x1b,0x5f,0x64,0xac]))]
encoded=[]
for name,desc,maxstack,maxlocals,code in methods:
 n=utf(name);t=utf(desc);body=u2(maxstack)+u2(maxlocals)+u4(len(code))+code+u2(0)+u2(0)
 encoded.append(u2(9)+u2(n)+u2(t)+u2(1)+u2(code_name)+u4(len(body))+body)
raw=b'\xca\xfe\xba\xbe'+u2(0)+u2(49)+u2(len(pool)+1)+b''.join(pool)+u2(0x21)+u2(this)+u2(parent)+u2(0)+u2(0)+u2(len(encoded))+b''.join(encoded)+u2(0)
driver='''import net.minecraft.test.StackFixture;
public class StackReference {
 public static void main(String[] a){int x=Integer.parseInt(a[1]), y=Integer.parseInt(a[2]);long z=Long.parseLong(a[3]);
  System.out.println(switch(a[0]){case "dupPair"->StackFixture.dupPair(x,y);case "popPair"->StackFixture.popPair(x,y);
   case "popLong"->StackFixture.popLong(z);case "dupLong"->StackFixture.dupLong(z);case "intSwap"->StackFixture.intSwap(x,y);default->throw new IllegalArgumentException();});}
}'''
with tempfile.TemporaryDirectory(prefix='mc-numeric-stack-') as tmp:
 d=pathlib.Path(tmp);target=d/'net/minecraft/test/StackFixture.class';target.parent.mkdir(parents=True);target.write_bytes(raw)
 (d/'StackReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(d),'-d',str(d),str(d/'StackReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 for name,desc,*_ in methods:
  subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile-numeric',str(d/'fixture.jar'),'net/minecraft/test/StackFixture',name,desc,str(d/name)],capture_output=True,text=True,check=True)
 values=[(-2147483648,2147483647,-9223372036854775808),(-1,2,-1),(0,0,0),(2147483647,-1,9223372036854775807)]
 for name,desc,*_ in methods:
  for x,y,z in values:
   ref=subprocess.run([str(jdk/'java'),'-cp',str(d),'StackReference',name,str(x),str(y),str(z)],capture_output=True,text=True,check=True).stdout.strip()
   args=[x,y] if desc.startswith('(II)') else [z]
   got=subprocess.run([str(d/name),*map(str,args)],capture_output=True,text=True,check=True).stdout.strip()
   if got!=ref:raise AssertionError((name,args,got,ref))
 print('OK: 20 comparaciones Java de pop2/dup2 para categorías 1/2 y swap')
