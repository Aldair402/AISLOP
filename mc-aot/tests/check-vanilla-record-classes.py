#!/usr/bin/env python3
"""Records integrales completos: constructor, accessors y ObjectMethods vs Java."""
import os
import pathlib
import random
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jar = root.parent / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
classes = [
 ('net/minecraft/network/protocol/game/VecDelta$Stepped$DeltaStep', [('xa','S'),('ya','S'),('za','S'),('ticks','I')]),
 ('net/minecraft/server/jsonrpc/IncomingRpcMethod$Attributes', [('runOnMainThread','Z'),('discoverable','Z'),('allowPreServerInit','Z')]),
 ('net/minecraft/server/jsonrpc/OutgoingRpcMethod$Attributes', [('discoverable','Z'),('allowPreServerInit','Z')]),
]
source = '''package net.minecraft.test;
public class Records {
 public record Mixed(int i,long l,boolean z,short s,char c,byte b) {}
 public record Empty() {}
 public record Decimal(float f) {}
}'''
DRIVER = '''import java.lang.reflect.*;import java.util.*;
public class Oracle {
 static Object arg(Class<?> t,String s) {
  if(t==boolean.class)return !s.equals("0"); if(t==short.class)return Short.parseShort(s);
  if(t==byte.class)return Byte.parseByte(s); if(t==char.class)return (char)Integer.parseInt(s);
  if(t==long.class)return Long.parseLong(s); if(t==int.class)return Integer.parseInt(s);
  throw new AssertionError(t);
 }
 static void print(Object v) {
  if(v==null){System.out.println("OK");return;}
  if(v instanceof Boolean){System.out.println((Boolean)v?"1":"0");return;}
  if(v instanceof Character){System.out.println((int)(Character)v);return;}
  if(v instanceof String){System.out.print("s16:");String s=(String)v;for(int i=0;i<s.length();i++)System.out.printf("%04x",(int)s.charAt(i));System.out.println();return;}
  System.out.println(v);
 }
 public static void main(String[] args) throws Exception {
  Class<?> c=Class.forName(args[0].replace('/','.'));var cs=c.getDeclaredConstructors();
  if(cs.length!=1)throw new AssertionError("constructores");Constructor<?> k=cs[0];k.setAccessible(true);
  var components=c.getRecordComponents();if(components==null)throw new AssertionError("no record");
  Set<String> expected=new HashSet<>(Arrays.asList("equals","hashCode","toString"));
  for(var comp:components)expected.add(comp.getName());
  Set<String> actual=new HashSet<>();for(var method:c.getDeclaredMethods())actual.add(method.getName());
  if(!actual.equals(expected)||c.getDeclaredMethods().length!=expected.size()||c.getDeclaredFields().length!=components.length)throw new AssertionError("superficie cambió");
  List<Object> objects=new ArrayList<>();Object current=null;
  for(String raw:args[1].split(";")) {String[] p=raw.split(",");
   if(p[0].equals("new")){Class<?>[] types=k.getParameterTypes();Object[] values=new Object[types.length];for(int i=0;i<types.length;i++)values[i]=arg(types[i],p[i+1]);current=k.newInstance(values);objects.add(current);System.out.println("OK");}
   else if(p[0].equals("select")){current=objects.get(Integer.parseInt(p[1].substring(1)));System.out.println("OK");}
   else if(p[0].equals("read")){Field f=c.getDeclaredField(p[1]);f.setAccessible(true);print(f.get(current));}
   else if(p[0].equals("equals")){Object other=p[1].equals("null")?null:objects.get(Integer.parseInt(p[1].substring(1)));print(c.getMethod("equals",Object.class).invoke(current,other));}
   else print(c.getMethod(p[0]).invoke(current));
  }
 }
}'''

def run(args, **kw):
 return subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=180,**kw)

def execute(d, classjar, name, fields, values):
 binary=d/('binary-'+str(len(list(d.glob('binary-*')))))
 compiled=run([compiler,'class-demo',classjar,name,binary]);assert compiled.returncode==0,(name,compiled.stderr)
 steps=[]
 for index, value in enumerate(values):
  steps.append(['new',*map(str,value)])
  for field,_ in fields:steps.extend([['read',field],[field]])
  steps.extend([['hashCode'],['toString'],['equals',f'@{index}'],['equals','null'],['equals','@0']])
  if index: steps.extend([['select','@0'],['equals',f'@{index}'],['select',f'@{index}']])
 script=';'.join(','.join(x) for x in steps);argv=[]
 for i,step in enumerate(steps):
  if i:argv.append('--')
  argv.extend(step)
 java=run([jdk/'java','-cp',f'{d}{os.pathsep}{classjar}','Oracle',name,script])
 native=run([binary,*argv],env=dict(os.environ,PATH='/nonexistent'))
 assert java.returncode==native.returncode==0,(name,java.stderr,native.stderr)
 assert java.stdout==native.stdout,(name,java.stdout,native.stdout)
 for steps_bad, reason in [(['equals','@0'],'objeto no construido'),
                           (['new',*map(str,values[0]),'--','equals','@99999'],'índice de objeto inexistente'),
                           (['new',*map(str,values[0]),'--','select','null'],'select no admite null'),
                           (['new',*map(str,values[0]),'--','equals','bogus'],'referencia inválida')]:
  r=run([binary,*steps_bad],env=dict(os.environ,PATH='/nonexistent'))
  assert r.returncode==2 and reason in r.stderr,(name,steps_bad,r.stderr)
 print(f'OK: {name}: constructor + todos los métodos/campos declarados, {len(values)} objetos y {len(steps)} pasos == Java 25 sin JVM')

with tempfile.TemporaryDirectory(prefix='vanilla-records-') as tmp:
 d=pathlib.Path(tmp);(d/'Records.java').write_text(source);(d/'Oracle.java').write_text(DRIVER)
 (d/'Dollar$Record.java').write_text('package net.minecraft.test; public record Dollar$Record(int n) {}')
 compiled=run([jdk/'javac','-d',d,d/'Records.java',d/'Oracle.java',d/'Dollar$Record.java']);assert compiled.returncode==0,compiled.stderr
 fixture=d/'fixture.jar';packed=run([jdk/'jar','cf',fixture,'-C',d,'net']);assert packed.returncode==0,packed.stderr
 rng=random.Random(20261109)
 for name, fields in classes:
  if fields[0][1]=='S':
   values=[(-32768,0,32767,-2147483648),(-32768,0,32767,-2147483648),(32767,-32768,-1,2147483647)]
   values += [(rng.randint(-32768,32767),rng.randint(-32768,32767),rng.randint(-32768,32767),rng.randint(-2147483648,2147483647)) for _ in range(37)]
  else:
   values=[tuple(0 for _ in fields),tuple(0 for _ in fields),tuple(1 for _ in fields)]
   values += [tuple(rng.randint(0,1) for _ in fields) for _ in range(37)]
  execute(d,jar,name,fields,values)
 mixed=[('i','I'),('l','J'),('z','Z'),('s','S'),('c','C'),('b','B')]
 execute(d,fixture,'net/minecraft/test/Records$Mixed',mixed,[(0,0,0,0,0,0),(-2147483648,-9223372036854775808,1,-32768,55296,-128),(-2147483648,-9223372036854775808,1,-32768,55296,-128),(2147483647,9223372036854775807,0,32767,65535,127)])
 execute(d,fixture,'net/minecraft/test/Records$Empty',[],[(),()])
 execute(d,fixture,'net/minecraft/test/Dollar$Record',[('n','I')],[(0,),(-2147483648,),(2147483647,)])
 bad=d/'bad-float';r=run([compiler,'class-demo',fixture,'net/minecraft/test/Records$Decimal',bad]);assert r.returncode!=0 and 'tipo no soportado: F' in r.stderr and not bad.exists(),r.stderr
