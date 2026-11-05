#!/usr/bin/env python3
"""Genera bytecode JVM para las nueve formas válidas dup*_x* y compara con Java."""
import os,pathlib,struct,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
u2=lambda n:struct.pack('>H',n);u4=lambda n:struct.pack('>I',n);pool=[]
def utf(s):
 b=s.encode();pool.append(b'\x01'+u2(len(b))+b);return len(pool)
def cl(i):pool.append(b'\x07'+u2(i));return len(pool)
this=cl(utf('net/minecraft/test/DupFixture'));parent=cl(utf('java/lang/Object'));code_name=utf('Code')
# x1: 1 forma; x2: 2; dup2_x1: 2; dup2_x2: 4.
methods=[
 ('x1','(II)I',4,2,[0x1a,0x1b,0x5a,0x64,0x64,0xac]),
 ('x2_111','(III)I',4,3,[0x1a,0x1b,0x1c,0x5b,0x64,0x64,0x64,0xac]),
 ('x2_21','(JI)I',4,3,[0x1e,0x1c,0x5b,0x57,0x88,0x64,0xac]),
 ('d2x1_111','(III)I',5,3,[0x1a,0x1b,0x1c,0x5d,0x64,0x64,0x64,0x64,0xac]),
 ('d2x1_12','(IJ)J',5,3,[0x1a,0x1f,0x5d,0x58,0x85,0x65,0xad]),
 ('d2x2_1111','(IIII)I',6,4,[0x1a,0x1b,0x1c,0x1d,0x5e,0x64,0x64,0x64,0x64,0x64,0xac]),
 ('d2x2_211','(JII)I',6,4,[0x1e,0x1c,0x1d,0x5e,0x64,0x57,0x88,0x64,0x64,0xac]),
 ('d2x2_112','(IIJ)J',6,4,[0x1a,0x1b,0x20,0x5e,0x58,0x64,0x85,0x65,0xad]),
 ('d2x2_22','(JJ)J',6,4,[0x1e,0x20,0x5e,0x65,0x65,0xad]),
]
encoded=[]
for name,desc,maxstack,maxlocals,code in methods:
 n=utf(name);t=utf(desc);code=bytes(code);body=u2(maxstack)+u2(maxlocals)+u4(len(code))+code+u2(0)+u2(0);encoded.append(u2(9)+u2(n)+u2(t)+u2(1)+u2(code_name)+u4(len(body))+body)
raw=b'\xca\xfe\xba\xbe'+u2(0)+u2(49)+u2(len(pool)+1)+b''.join(pool)+u2(0x21)+u2(this)+u2(parent)+u2(0)+u2(0)+u2(len(encoded))+b''.join(encoded)+u2(0)
driver='''import net.minecraft.test.DupFixture;
public class DupReference {public static void main(String[] s){int a=Integer.parseInt(s[1]),b=Integer.parseInt(s[2]),c=Integer.parseInt(s[3]),d=Integer.parseInt(s[4]);long x=Long.parseLong(s[5]),y=Long.parseLong(s[6]);
System.out.println(switch(s[0]){case "x1"->DupFixture.x1(a,b);case "x2_111"->DupFixture.x2_111(a,b,c);case "x2_21"->DupFixture.x2_21(x,a);case "d2x1_111"->DupFixture.d2x1_111(a,b,c);case "d2x1_12"->DupFixture.d2x1_12(a,x);case "d2x2_1111"->DupFixture.d2x2_1111(a,b,c,d);case "d2x2_211"->DupFixture.d2x2_211(x,a,b);case "d2x2_112"->DupFixture.d2x2_112(a,b,x);case "d2x2_22"->DupFixture.d2x2_22(x,y);default->throw new IllegalArgumentException();});}}'''
with tempfile.TemporaryDirectory(prefix='mc-dup-x-') as t:
 d=pathlib.Path(t);target=d/'net/minecraft/test/DupFixture.class';target.parent.mkdir(parents=True);target.write_bytes(raw);(d/'DupReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(d),'-d',str(d),str(d/'DupReference.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 for name,desc,*_ in methods:subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile-numeric',str(d/'fixture.jar'),'net/minecraft/test/DupFixture',name,desc,str(d/name)],capture_output=True,text=True,check=True)
 values=[(-2147483648,2147483647,-123,999,-9223372036854775808,9223372036854775807),(-1,2,3,4,-1,19),(0,0,0,0,0,0),(2147483647,-1,97,-77,9223372036854775807,-9223372036854775808)]
 for name,desc,*_ in methods:
  for a,b,c,e,x,y in values:
   ref=subprocess.run([str(jdk/'java'),'-cp',str(d),'DupReference',name,*map(str,[a,b,c,e,x,y])],capture_output=True,text=True,check=True).stdout
   inputs={'x1':[a,b],'x2_111':[a,b,c],'x2_21':[x,a],'d2x1_111':[a,b,c],'d2x1_12':[a,x],'d2x2_1111':[a,b,c,e],'d2x2_211':[x,a,b],'d2x2_112':[a,b,x],'d2x2_22':[x,y]}[name]
   got=subprocess.run([str(d/name),*map(str,inputs)],capture_output=True,text=True,check=True).stdout
   if got!=ref:raise AssertionError((name,inputs,got,ref))
 print(f'OK: {len(methods)*len(values)} comparaciones Java; nueve formas de dup_x1/dup_x2/dup2_x1/dup2_x2')
