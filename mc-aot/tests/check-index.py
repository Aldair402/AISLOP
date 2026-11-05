#!/usr/bin/env python3
"""Comprueba descriptores, switches, handlers y MUTF-8 con un .class real de javac."""
import csv,io,os,pathlib,struct,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;
public class UtfFixture {
 public static final String VALUE="\0😀\uD800";
 public static int lookup(int x) { switch(x){case -7:return 1;case 100:return 2;case 9000:return 3;default:return 0;} }
 public static int table(int x) { switch(x){case 1:return 1;case 2:return 2;case 3:return 3;case 4:return 4;default:return 0;} }
 public static long arrays(String[][] x,long a,double b) { try {return x.length+a+(long)b;} catch (RuntimeException e) {return -1;} }
}'''
with tempfile.TemporaryDirectory(prefix='mc-index-test-') as tmp:
 d=pathlib.Path(tmp);(d/'UtfFixture.java').write_text(source,encoding='utf8')
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UtfFixture.java')],check=True)
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','index-dir',str(d)]
 p=subprocess.run(cmd,capture_output=True,text=True,check=True)
 rows=list(csv.DictReader(io.StringIO(p.stdout),delimiter='\t'))
 if len(rows)!=1 or rows[0]['clase']!='net/minecraft/test/UtfFixture':raise AssertionError(rows)
 if int(rows[0]['saltos'])<2 or int(rows[0]['manejadores_excepcion'])<1:raise AssertionError(rows)
 # Añade un MethodType con una clase que no aparece en ningún otro lugar del pool.
 # Esto comprueba que se conserva el índice del descriptor y se extrae la arista.
 cls=d/'net/minecraft/test/UtfFixture.class'; raw=cls.read_bytes()
 n=struct.unpack_from('>H',raw,8)[0]; pos=10; i=1
 while i<n:
  tag=raw[pos];pos+=1
  if tag==1:
   size=struct.unpack_from('>H',raw,pos)[0];pos+=2+size
  elif tag in (3,4,9,10,11,12,17,18):pos+=4
  elif tag in (5,6):pos+=8;i+=1
  elif tag in (7,8,16,19,20):pos+=2
  elif tag==15:pos+=3
  else:raise AssertionError(('tag CP',tag))
  i+=1
 extra=b'()Lmethodtype/Unique;'
 modified=raw[:8]+struct.pack('>H',n+2)+raw[10:pos]+bytes([1])+struct.pack('>H',len(extra))+extra+bytes([16])+struct.pack('>H',n)+raw[pos:]
 cls.write_bytes(modified)
 graph=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','graph-dir',str(d)],capture_output=True,text=True,check=True)
 edges={r['dependencia'] for r in csv.DictReader(io.StringIO(graph.stdout),delimiter='\t')}
 if 'methodtype/Unique' not in edges:raise AssertionError('dependencia MethodType perdida')
 (d/'bad.class').write_bytes(b'\xca\xfe\xba\xbe\x00')
 fail=subprocess.run(cmd,capture_output=True,text=True)
 if fail.returncode==0 or 'bad.class' not in fail.stderr:raise AssertionError('archivo truncado no rechazado')
 print('OK: MUTF-8, firmas, MethodType, switches y handlers; clase truncada rechazada')
