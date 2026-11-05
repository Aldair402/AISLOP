#!/usr/bin/env python3
"""Dos expresiones concretas de tokenización Log4j, comparadas con java.util.regex."""
import json,os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
rng=random.Random(42079);items=['','log4j2.foo','LOG4J.foo','org.apache.logging.log4j.name','AsyncLoggerConfig.test','xAsyncLogger.foo','abc_ABC123Foo','😀x_A9É','log4j22','LOG4J2','blah-123ABC','🧱']
for _ in range(100):items.append(''.join(rng.choice('abcxyzABCXYZ012345-. _/é😀') for _ in range(rng.randrange(0,19))))
literals=','.join(json.dumps(x,ensure_ascii=True) for x in items)
source=r'''package net.minecraft.test;import java.util.regex.*;public class RegexProbe{
 static final String[] WORDS=new String[]{%s};
 static String text(int n){return WORDS[n/8];}static int pos(int n,String s){switch(n%%8){case 0:return 0;case 1:return 1;case 2:return -1;case 3:return s.length();case 4:return s.length()+1;case 5:return s.length()/2;case 6:return 2;default:return 3;}}
 public static int run(int n){String s=text(n);try{Pattern p=Pattern.compile("([A-Z]*[a-z0-9]+|[A-Z0-9]+)[-._/]?");Matcher m=p.matcher(s);boolean found=m.find(pos(n,s));if(!found){try{m.end();return -12;}catch(IllegalStateException e){return -10;}}return m.group(1).hashCode()*31+m.end();}catch(IndexOutOfBoundsException e){return -20;}}
 public static int mutable(int n){StringBuilder b=new StringBuilder("AB12");Matcher m=Pattern.compile("([A-Z]*[a-z0-9]+|[A-Z0-9]+)[-._/]?").matcher(b);if(!m.find(0))return -1;b.append("x");int v=m.group(1).hashCode();if((n&1)!=0)try{m.find(-1);}catch(IndexOutOfBoundsException e){}if(m.end()!=4)return -2;if((n&2)!=0){if(!m.find(4))return -3;v=v*31+m.group(1).hashCode();}return v;}
 public static int prefix(int n){String s=text(n);try{Pattern p=Pattern.compile("(^log4j2?[-._/]|^org\\.apache\\.logging\\.log4j\\.)|(?=AsyncLogger(Config)?\\.)",2);Matcher m=p.matcher(s);return m.find(pos(n,s))?m.end()+1:0;}catch(IndexOutOfBoundsException e){return -20;}}
}''' % literals
# Make optional separator exactly match Log4j pattern.
source=source.replace('2?[-._/]','2?[-._/]?')
driver='''import net.minecraft.test.RegexProbe;public class Driver{public static void main(String[]a){for(int i=1;i<a.length;i++){int n=Integer.parseInt(a[i]);System.out.println(a[0].equals("run")?RegexProbe.run(n):a[0].equals("mutable")?RegexProbe.mutable(n):RegexProbe.prefix(n));}}}'''
with tempfile.TemporaryDirectory(prefix='mc-log4j-regex-') as t:
 d=pathlib.Path(t);(d/'RegexProbe.java').write_text(source);(d/'Driver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'RegexProbe.java'),str(d/'Driver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 seq=list(range(len(items)*8))
 for method in ['run','prefix']:
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RegexProbe',str(d/method),method,'(I)I'],capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError((method,p.stderr))
  # Bound heap to avoid exhausting the experimental arena across 896 cases.
  for off in range(0,len(seq),112):
   part=seq[off:off+112];j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver',method,*map(str,part)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/method),*[v for x in part for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
   if j!=n:
    jl=j.splitlines();nl=n.splitlines();k=next(i for i,(a,b) in enumerate(zip(jl,nl)) if a!=b);raise AssertionError((method,part[k],items[part[k]//8],jl[k],nl[k]))
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/RegexProbe',str(d/'mutable'),'mutable','(I)I'],capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(('mutable',p.stderr))
 vals=list(range(40));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'Driver','mutable',*map(str,vals)],capture_output=True,text=True,check=True).stdout;n=subprocess.run([str(d/'mutable'),*[v for x in vals for v in ('0',str(x))]],capture_output=True,text=True,check=True).stdout
 if j!=n:raise AssertionError(('mutable',j,n))
 print(f'OK: {len(seq)*2+len(vals)} resultados Java Matcher.find/end/group para dos patrones Log4j, posiciones, Unicode y entrada mutable')
