#!/usr/bin/env python3
"""new activa <clinit> antes de evaluar argumentos, con ciclos y constructores encadenados."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;
public class ObjectInit {
 static int phase=1;static R r=new R(Peer.get());static int after=phase;
 static int bump(){return ++phase;}
 static int probe(){return phase*10+(r==null?1:0);}
 public static int state(){return after*1000+r.value*10+R.seed;}
 public static int next(){return new R().value*10+R.seed;}
 public static void zap(){r=null;}
 public static int nullRead(){return r.value;}
}
class R {static int seed=ObjectInit.bump();int value;R(){this(9);}R(int v){value=v;}}
class Peer {static int x=ObjectInit.probe();static int get(){return x;}}
'''
driver='''import net.minecraft.test.ObjectInit;
public class ObjectInitDriver{public static void main(String[] a){System.out.println(ObjectInit.state());System.out.println(ObjectInit.next());System.out.println(ObjectInit.state());ObjectInit.zap();System.out.println("OK");try {ObjectInit.nullRead();}catch(NullPointerException e){System.out.println(e.getClass().getSimpleName());}}}'''
with tempfile.TemporaryDirectory(prefix='mc-object-init-') as t:
 d=pathlib.Path(t);(d/'ObjectInit.java').write_text(source);(d/'ObjectInitDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'ObjectInit.java'),str(d/'ObjectInitDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/ObjectInit',str(d/'native'),'state','()I','next','()I','zap','()V','nullRead','()I']
 p=subprocess.run(cmd,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d),'ObjectInitDriver'],capture_output=True,text=True,check=True).stdout.splitlines()
 p=subprocess.run([str(d/'native'),'0','1','0','2','3'],capture_output=True,text=True)
 if p.returncode!=2 or 'NullPointerException' not in p.stderr or p.stdout.splitlines()!=java[:-1] or java[-1]!='NullPointerException':raise AssertionError((java,p.stdout,p.stderr,p.returncode))
 if java[:3]!=['2212','92','2212']:raise AssertionError(java)
 print('OK: new inicializa antes de argumentos, ciclos interclase, constructores encadenados y null coinciden con Java 25')
