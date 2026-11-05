#!/usr/bin/env python3
"""Operaciones F/D, conversiones, NaN, ceros firmados y campos: diferencial Java 25."""
import os,pathlib,subprocess,tempfile,random
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;public class FpDemo {
 static float sf;static double sd;float f;double d;static float fid(float x){return x;}static double did(double x){return x;}
 public static int fop(int a,int b,int op){float x=Float.intBitsToFloat(a),y=Float.intBitsToFloat(b),z;switch(op){case 0:z=x+y;break;case 1:z=x-y;break;case 2:z=x*y;break;case 3:z=x/y;break;case 4:z=x%y;break;case 5:z=-x;break;case 6:sf=x;z=sf;break;case 7:FpDemo q=new FpDemo();q.f=x;z=q.f;break;case 8:z=fid(x);break;case 9:return x<y?-1:x>y?1:x==y?0:99;case 10:return (int)x;case 11:return (int)(long)x;case 12:z=(float)(double)x;break;case 13:return Float.floatToRawIntBits(x);default:return (int)(double)x;}return Float.floatToIntBits(z);}
 public static long dop(long a,long b,int op){double x=Double.longBitsToDouble(a),y=Double.longBitsToDouble(b),z;switch(op){case 0:z=x+y;break;case 1:z=x-y;break;case 2:z=x*y;break;case 3:z=x/y;break;case 4:z=x%y;break;case 5:z=-x;break;case 6:sd=x;z=sd;break;case 7:FpDemo q=new FpDemo();q.d=x;z=q.d;break;case 8:z=did(x);break;case 9:return x<y?-1:x>y?1:x==y?0:99;case 10:return (int)x;case 11:return (long)x;case 12:z=(double)(float)x;break;case 13:return Double.doubleToRawLongBits(x);default:return (long)(float)x;}return Double.doubleToLongBits(z);}
}'''
driver='''import net.minecraft.test.FpDemo;public class FpDriver{public static void main(String[]a){for(int i=0;i<a.length;i+=4){int op=Integer.parseInt(a[i+3]);if(a[i].equals("f"))System.out.println(FpDemo.fop(Integer.parseInt(a[i+1]),Integer.parseInt(a[i+2]),op));else System.out.println(FpDemo.dop(Long.parseLong(a[i+1]),Long.parseLong(a[i+2]),op));}}}'''
def signed(x,n):return x-(1<<n) if x&(1<<(n-1)) else x
with tempfile.TemporaryDirectory(prefix='mc-float-') as t:
 d=pathlib.Path(t);(d/'FpDemo.java').write_text(src);(d/'FpDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FpDemo.java'),str(d/'FpDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FpDemo',str(d/'native'),'fop','(III)I','dop','(JJI)J'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 r=random.Random(28);fs=[0,0x80000000,1,0x80000001,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00000]+[r.getrandbits(32) for _ in range(8)];ds=[0,0x8000000000000000,1,0x8000000000000001,0x3ff0000000000000,0xbff0000000000000,0x7fefffffffffffff,0xffefffffffffffff,0x7ff0000000000000,0xfff0000000000000,0x7ff8000000000000]+[r.getrandbits(64) for _ in range(8)]
 cases=[]
 for label,values,bits in [('f',fs,32),('d',ds,64)]:
  for i,a in enumerate(values):
   for op in range(15):cases.append((label,str(signed(a,bits)),str(signed(values[(i*7+3)%len(values)],bits)),str(op)))
 ja=subprocess.run([str(jdk/'java'),'-cp',str(d),'FpDriver',*[x for c in cases for x in c]],capture_output=True,text=True,check=True).stdout.splitlines();na=subprocess.run([str(d/'native'),*[x for label,a,b,op in cases for x in ('0' if label=='f' else '1',a,b,op)]],capture_output=True,text=True,check=True).stdout.splitlines()
 for c,x,y in zip(cases,ja,na):
  if x!=y:raise AssertionError((c,x,y))
 if len(ja)!=len(na) or len(ja)!=len(cases):raise AssertionError((len(ja),len(na),len(cases)))
 print(f'OK: {len(cases)} comparaciones F/D Java, IEEE, NaN, ±0, conversiones, campos y llamadas')
