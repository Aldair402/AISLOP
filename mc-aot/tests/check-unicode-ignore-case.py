#!/usr/bin/env python3
"""Fold Unicode Java 25, pares suplementarios y sustitutos aislados; contraste muestreado."""
import base64,os,pathlib,random,re,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
# Escapes literales Java; incluyen pares, sustitutos aislados, secuencias mal formadas y longitudes mixtas.
literals=['""','"a"','"A"','"\\u0130"','"i"','"\\u0131"','"\\u00df"','"\\u1e9e"','"\\ud800"','"\\ud801"','"\\udc00"','"\\udc01"','"\\ud801\\udc00"','"\\ud801\\udc28"','"\\ud800\\udc00"','"\\ud800x"','"\\ud800X"','"x\\udc00"','"X\\udc00"','"\\ud800\\ud800"','"\\udc00\\ud800"','"\\ud800\\udc00x"','"\\ud800\\udc00X"']
source='''package net.minecraft.test;
public class UnicodeCase {static String[] malformed={LITERALS};public static int eq(String a,String b){return a.equalsIgnoreCase(b)?1:0;}public static int bad(int a,int b){return malformed[a].equalsIgnoreCase(malformed[b])?1:0;}}
'''.replace('LITERALS',','.join(literals))
driver='''import net.minecraft.test.UnicodeCase;import java.io.*;import java.util.Base64;import java.nio.charset.StandardCharsets;
public class UnicodeCaseDriver {public static void main(String[] z)throws Exception{BufferedReader r=new BufferedReader(new InputStreamReader(System.in));String s;while((s=r.readLine())!=null){String[] x=s.split("\\t",-1);if(x[0].equals("m"))System.out.println(UnicodeCase.bad(Integer.parseInt(x[1]),Integer.parseInt(x[2])));else System.out.println(UnicodeCase.eq(new String(Base64.getDecoder().decode(x[1]),StandardCharsets.UTF_8),new String(Base64.getDecoder().decode(x[2]),StandardCharsets.UTF_8)));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-unicode-ignore-case-') as t:
 d=pathlib.Path(t);(d/'UnicodeCase.java').write_text(source);(d/'UnicodeCaseDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'UnicodeCase.java'),str(d/'UnicodeCaseDriver.java'),str(root/'tools/CaseFoldJava25.java')],check=True)
 generated=subprocess.run([str(jdk/'java'),'-cp',str(d),'CaseFoldJava25'],capture_output=True,text=True,check=True).stdout
 mapping=[tuple(int(x,16) for x in line.split()) for line in generated.splitlines()]
 table=[tuple(int(x,16) for x in pair) for pair in re.findall(r'\(0x([0-9a-f]+),0x([0-9a-f]+)\)',(root/'src/unicode_casefold_java25.inc').read_text())]
 if mapping!=table:raise AssertionError('la tabla persistida no corresponde al Java 25 de referencia')
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/UnicodeCase',str(d/'native'),'eq','(Ljava/lang/String;Ljava/lang/String;)I','bad','(II)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 rows=[];enc=lambda s:base64.b64encode(s.encode()).decode()
 def add(a,b):rows.append(('u',a,b))
 for c,f in mapping:
  if c!=0 and f!=0 and not (0xd800<=c<=0xdfff or 0xd800<=f<=0xdfff):add(chr(c),chr(f));add('X'+chr(c)+'z','x'+chr(f)+'Z')
 special=[('İ','i'),('ı','I'),('ß','ẞ'),('Σ','ς'),('ſ','S'),('K','k'),('𐐀','𐐨'),('😀','😀'),('ß','SS'),('ﬀ','FF')]
 rows.extend(('u',a,b) for a,b in special)
 rng=random.Random(2516);values=[c for c,f in mapping if c!=0 and not 0xd800<=c<=0xdfff]
 for _ in range(4000):
  a=rng.choice(values);b=rng.choice(values);add(chr(a),chr(b))
 rows.extend(('m',i,j) for i in range(len(literals)) for j in range(len(literals)))
 inp=''.join(('u\t'+enc(a)+'\t'+enc(b)+'\n') if k=='u' else f'm\t{a}\t{b}\n' for k,a,b in rows)
 ref=subprocess.run([str(jdk/'java'),'-cp',str(d),'UnicodeCaseDriver'],input=inp,capture_output=True,text=True,check=True).stdout.splitlines()
 if len(ref)!=len(rows):raise AssertionError(('java output',len(ref),len(rows)))
 got=[]
 for off in range(0,len(rows),400):
  args=[]
  for k,a,b in rows[off:off+400]:args+=['0','s:'+a,'s:'+b] if k=='u' else ['1',str(a),str(b)]
  result=subprocess.run([str(d/'native'),*args],capture_output=True,text=True,check=True).stdout.splitlines();got.extend(result)
 if ref!=got:
  i=next((i for i,(a,b) in enumerate(zip(ref,got)) if a!=b),min(len(ref),len(got)));raise AssertionError((i,rows[i],ref[i:i+1],got[i:i+1]))
 print(f'OK: {len(mapping)} mapeos Java 25 reproducidos; {len(rows)} comparaciones Java Unicode, suplementarios y sustitutos aislados')
