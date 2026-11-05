#!/usr/bin/env python3
"""Sonda diagnóstica: TracingExecutor.class oficial sin sustituir; no certifica el arranque."""
import os, pathlib, subprocess, tempfile, zipfile
root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
inner = root.parent / 'downloads/server-26.3-inner.jar'
source = '''package net.minecraft.test;
import java.util.concurrent.*; import net.minecraft.TracingExecutor;
public class RealTracingProbe {
 public static int run(int n) {
  TracingExecutor t = new TracingExecutor(new ForkJoinPool(1));
  t.shutdownAndAwait(1L, TimeUnit.SECONDS);
  return n;
 }
}'''
driver = '''import net.minecraft.test.RealTracingProbe;
public class Driver {public static void main(String[] args){System.out.println(RealTracingProbe.run(42));}}'''
with tempfile.TemporaryDirectory(prefix='mc-tracing-real-') as temp:
 d=pathlib.Path(temp); (d/'RealTracingProbe.java').write_text(source); (d/'Driver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),str(d/'RealTracingProbe.java'),str(d/'Driver.java')],check=True)
 # Se conserva byte a byte el archivo original y no se reemplaza con stubs.
 with zipfile.ZipFile(inner) as z:
  p=d/'net/minecraft/TracingExecutor.class'; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(z.read('net/minecraft/TracingExecutor.class'))
 subprocess.run([str(jdk/'jar'),'cf',str(d/'probe.jar'),'-C',str(d),'net'],check=True)
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(inner),'Driver'],text=True,capture_output=True,timeout=15)
 print('Java exit:',java.returncode,'stdout:',repr(java.stdout),'stderr:',repr(java.stderr))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','concurrent-rayon-int-demo',str(d/'probe.jar'),'net/minecraft/test/RealTracingProbe',str(d/'probe'),'run','(I)I'],text=True,capture_output=True,timeout=90)
 print('AOT compile exit:',p.returncode,'stdout:',repr(p.stdout),'stderr:',repr(p.stderr))
 if java.returncode or java.stdout!='42\n': raise RuntimeError('Falló el oráculo Java real')
 if p.returncode == 0:
  native=subprocess.run([str(d/'probe'),'42'],text=True,capture_output=True,timeout=15)
  print('AOT run exit:',native.returncode,'stdout:',repr(native.stdout),'stderr:',repr(native.stderr))
  if native.returncode or native.stdout != java.stdout: raise RuntimeError('Discrepancia con Java')
