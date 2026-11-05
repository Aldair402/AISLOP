#!/usr/bin/env python3
"""Traduce 3 métodos oficiales QuartPos a frames compartidos ejecutados por hilos Rust."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';workspace=root.parent
source='''import net.minecraft.core.QuartPos;public class QuartDriver{public static void main(String[] a){String op=a[0];for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(op.equals("quartLocal")?QuartPos.quartLocal(n):op.equals("fromBlock")?QuartPos.fromBlock(n):QuartPos.toBlock(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-concurrent-quart-') as t:
 d=pathlib.Path(t);(d/'QuartDriver.java').write_text(source);jar=workspace/'downloads/server-26.3-inner.jar';subprocess.run([str(jdk/'javac'),'-cp',str(jar),'-d',str(d),str(d/'QuartDriver.java')],check=True)
 rng=random.Random(26);vals=[-2147483648,2147483647,-1,0,1]+[rng.randint(-2147483648,2147483647) for _ in range(200)]
 for method in ['quartLocal','fromBlock','toBlock']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--',os.environ.get('MC_AOT_CONCURRENT_BACKEND','concurrent-int-demo'),str(workspace/'downloads/server-26.3.jar'),'net/minecraft/core/QuartPos',str(d/method),method,'(I)I'],capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
  j=subprocess.run([str(jdk/'java'),'-cp',str(jar)+os.pathsep+str(d),'QuartDriver',method,*map(str,vals)],capture_output=True,text=True,check=True).stdout;a=subprocess.run([str(d/method),*map(str,vals)],capture_output=True,text=True)
  if a.returncode or j!=a.stdout:raise AssertionError((method,a.returncode,j,a.stdout,a.stderr))
 print('OK: 615 resultados de tres métodos oficiales QuartPos ejecutados en frames y workers Rust')
