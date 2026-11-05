#!/usr/bin/env python3
"""InternalError y VirtualMachineError: jerarquía, causa y mensaje."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;public class InternalErrorProbe{public static int run(int n){RuntimeException cause=new RuntimeException("cause");try{if(n%3==0)throw new InternalError("oops");if(n%3==1)throw new InternalError("oops",cause);throw new InternalError(cause);}catch(VirtualMachineError e){return (e instanceof InternalError?1:0)+(e.getCause()==cause?2:0)+(e.getMessage()!=null?e.getMessage().hashCode():0);}}}'''
driver='''import net.minecraft.test.InternalErrorProbe;public class Driver{public static void main(String[]a){for(String n:a)System.out.println(InternalErrorProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-internal-error-') as t:
 d=pathlib.Path(t);(d/'InternalErrorProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'InternalErrorProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/InternalErrorProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 seq=list(range(-40,41));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',*map(str,seq)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'native'),*[v for x in seq for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError((j,n))
 print(f'OK: {len(seq)} casos InternalError/VirtualMachineError y causas/mensajes')
