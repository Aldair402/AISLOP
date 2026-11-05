#!/usr/bin/env python3
"""Construye .class con ConstantValue leído por getstatic, para evitar inlining de javac."""
import os,pathlib,struct,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
u2=lambda n:struct.pack('>H',n);u4=lambda n:struct.pack('>I',n)
pool=[]
def item(raw,wide=False):
 pool.append(raw);i=len(pool)
 if wide:pool.append(None)
 return i
def utf(s):b=s.encode();return item(b'\x01'+u2(len(b))+b)
def cls(i):return item(b'\x07'+u2(i))
def nt(n,d):return item(b'\x0c'+u2(n)+u2(d))
def field(owner,n,d):return item(b'\x09'+u2(owner)+u2(nt(n,d)))
def integer(x):return item(b'\x03'+struct.pack('>i',x))
def long(x):return item(b'\x05'+struct.pack('>q',x),True)
this=cls(utf('net/minecraft/test/ConstFixture'));parent=cls(utf('java/lang/Object'));code_name=utf('Code');constant_name=utf('ConstantValue')
spec=[('IV','I',-2147483648),('LV','J',-9223372036854775808),('BV','B',-128),('CV','C',65535),('SV','S',-32768),('ZV','Z',1)]
fields=[];refs=[]
for name,desc,value in spec:
 n=utf(name);d=utf(desc);const=long(value) if desc=='J' else integer(value);refs.append(field(this,n,d))
 attr=u2(constant_name)+u4(2)+u2(const);fields.append(u2(0x0019)+u2(n)+u2(d)+u2(1)+attr)
derived_name=utf('derived');desc_i=utf('I');derived_ref=field(this,derived_name,desc_i);fields.append(u2(0x000a)+u2(derived_name)+u2(desc_i)+u2(0))
methods=[];selected=[]
def method(name,desc,code,maxstack):
 body=u2(maxstack)+u2(0)+u4(len(code))+code+u2(0)+u2(0)
 methods.append(u2(0x0008 if name=='<clinit>' else 0x0009)+u2(utf(name))+u2(utf(desc))+u2(1)+u2(code_name)+u4(len(body))+body)
for (name,desc,_),ref in zip(spec,refs):
 meth='get'+name; method(meth,'()'+desc,b'\xb2'+u2(ref)+(b'\xad' if desc=='J' else b'\xac'),2 if desc=='J' else 1);selected.append((meth,'()'+desc))
method('<clinit>','()V',b'\xb2'+u2(refs[0])+b'\x04\x60\xb3'+u2(derived_ref)+b'\xb1',2)
method('getDerived','()I',b'\xb2'+u2(derived_ref)+b'\xac',1);selected.append(('getDerived','()I'))
raw=b'\xca\xfe\xba\xbe'+u2(0)+u2(49)+u2(len(pool)+1)+b''.join(v for v in pool if v is not None)+u2(0x21)+u2(this)+u2(parent)+u2(0)+u2(len(fields))+b''.join(fields)+u2(len(methods))+b''.join(methods)+u2(0)
driver='''import net.minecraft.test.ConstFixture;
public class ConstReference {public static void main(String[] a){System.out.println(ConstFixture.getIV());System.out.println(ConstFixture.getLV());System.out.println(ConstFixture.getBV());System.out.println((int)ConstFixture.getCV());System.out.println(ConstFixture.getSV());System.out.println(ConstFixture.getZV()?1:0);System.out.println(ConstFixture.getDerived());}}'''
with tempfile.TemporaryDirectory(prefix='mc-constant-test-') as tmp:
 d=pathlib.Path(tmp);target=d/'net/minecraft/test/ConstFixture.class';target.parent.mkdir(parents=True);target.write_bytes(raw);(d/'ConstReference.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(d),'-d',str(d),str(d/'ConstReference.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'test.jar'),'-C',str(d),'net'],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','static-demo',str(d/'test.jar'),'net/minecraft/test/ConstFixture',str(d/'native')]
 for name,desc in selected:cmd.extend([name,desc])
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ConstReference'],capture_output=True,text=True,check=True).stdout.splitlines()
 native=subprocess.run([str(d/'native'),*map(str,range(len(selected)))],capture_output=True,text=True,check=True).stdout.splitlines()
 if java!=native:raise AssertionError((java,native))
 print('OK: 6 ConstantValue I/J/B/C/S/Z y lectura desde <clinit> coinciden con Java 25')
