#!/usr/bin/env python3
"""Patrón de duración literal de Log4j; no implementa matcher."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source=r'''package net.minecraft.test;import java.util.regex.Pattern;public class DurationPatternProbe {
 public static int run(int n){try{String text=n==0?null:"([+-]?\\d+)\\s*(\\w+)?";Pattern p=Pattern.compile(text,Pattern.CASE_INSENSITIVE);return (p.pattern()==text?1:0)+(p.toString()==text?2:0)+(p.flags()==2?4:0);}catch(NullPointerException e){return 9;}}
 public static int badFlags(int n){return Pattern.compile("([+-]?\\d+)\\s*(\\w+)?",0).flags();}
 public static int badPattern(int n){return Pattern.compile(".*",2).flags();}
 public static int matcher(int n){return Pattern.compile("([+-]?\\d+)\\s*(\\w+)?",2).matcher("5ms").matches()?1:0;}
}'''
driver='''import net.minecraft.test.DurationPatternProbe;public class DurationPatternDriver{public static void main(String[]a){for(String n:a)System.out.println(DurationPatternProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-pattern-duration-') as tmp:
 d=pathlib.Path(tmp);(d/'DurationPatternProbe.java').write_text(source);(d/'DurationPatternDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'DurationPatternProbe.java'),str(d/'DurationPatternDriver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/DurationPatternProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'DurationPatternDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 for method,want in [('badFlags','flags fuera del perfil'),('badPattern','expresión regular fuera del perfil')]:
  p=compile(method)
  if p.returncode:raise RuntimeError(p.stderr)
  n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
  if n.returncode==0 or want not in n.stderr:raise AssertionError((method,n.stderr))
 p=compile('matcher')
 if p.returncode:raise RuntimeError(p.stderr)
 n=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
 if n.returncode==0 or 'Pattern.matcher: expresión fuera del perfil' not in n.stderr:raise AssertionError(('matcher guard',n.stderr))
 print(f'OK: {len(vals)} resultados Pattern de duración de Log4j, identidad, flags y null; guardas de patrón, flags y matcher')
