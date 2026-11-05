#!/usr/bin/env python3
"""Rechaza rangos, destinos y tipos Class inválidos en la tabla de excepciones."""
import os,pathlib,struct,subprocess,sys,tempfile
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));import scan_bytecode
jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test; public class BadHandler {public static int f(int n){try{return 10/n;}catch(ArithmeticException e){return -1;}}}'''
with tempfile.TemporaryDirectory(prefix='mc-handler-table-') as t:
 d=pathlib.Path(t);(d/'BadHandler.java').write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'BadHandler.java')],check=True)
 cls=d/'net/minecraft/test/BadHandler.class';original=cls.read_bytes();r=scan_bytecode.R(original)
 r.take(8);size=r.u2();cp=[None]*size;i=1
 while i<size:
  tag=r.u1()
  if tag==1:cp[i]=r.take(r.u2()).decode('utf8','replace')
  elif tag in (3,4):r.take(4)
  elif tag in (5,6):r.take(8);i+=1
  elif tag in (7,8,16,19,20):r.take(2)
  elif tag in (9,10,11,12,17,18):r.take(4)
  elif tag==15:r.take(3)
  else:raise AssertionError(tag)
  i+=1
 r.take(6);r.take(2*r.u2())
 for _ in range(r.u2()):r.take(6);list(scan_bytecode.attrs(r))
 offset=None
 for _ in range(r.u2()):
  flags=r.u2();name=cp[r.u2()];desc=cp[r.u2()];count=r.u2()
  for _ in range(count):
   aname=cp[r.u2()];length=r.u4();start=r.p;data=r.take(length)
   if name=='f' and aname=='Code':
    cr=scan_bytecode.R(data);cr.take(4);cr.take(cr.u4());assert cr.u2()>0;offset=start+cr.p
 assert offset is not None
 for label,delta,value,expected in [('start',0,65535,'rango o destino inválido'),('end',2,65535,'rango o destino inválido'),('target',4,65535,'rango o destino inválido'),('class',6,65535,'tipo de excepción Class inválido')]:
  bad=bytearray(original);struct.pack_into('>H',bad,offset+delta,value);cls.write_bytes(bad)
  subprocess.run([str(jdk/'jar'),'cf',str(d/'bad.jar'),'-C',str(d),'net'],check=True)
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','compile',str(d/'bad.jar'),'net/minecraft/test/BadHandler','f','(I)I',str(d/'out')],capture_output=True,text=True)
  if p.returncode==0 or expected not in p.stderr or (d/'out').exists():raise AssertionError((label,p.returncode,p.stderr))
 print('OK: cuatro tablas de excepciones malformadas rechazadas: inicio, fin, destino y Class')
