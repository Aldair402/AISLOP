#!/usr/bin/env python3
"""LinkedHashSet(int) y orden para claves String/null."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.*;public class SetCapacityProbe{
 public static int run(int n){try{LinkedHashSet<String> s=new LinkedHashSet<>(n);s.add("a");s.add(null);s.add("b");s.add("a");Iterator<String> i=s.iterator();return s.size()*10+(i.next().equals("a")&&i.next()==null&&i.next().equals("b")?1:0);}catch(IllegalArgumentException e){return e.getMessage().equals("Illegal initial capacity: -1")?100:101;}}
 public static int big(int n){return new LinkedHashSet<String>(1000001).size();}
}'''
driver='''import net.minecraft.test.SetCapacityProbe;public class SetCapacityDriver{public static void main(String[]a){for(String n:a)System.out.println(SetCapacityProbe.run(Integer.parseInt(n)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-set-capacity-') as tmp:
 d=pathlib.Path(tmp);(d/'SetCapacityProbe.java').write_text(source);(d/'SetCapacityDriver.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'SetCapacityProbe.java'),str(d/'SetCapacityDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 def compile(method):return subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/SetCapacityProbe',str(d/'native'),method,'(I)I'],capture_output=True,text=True,timeout=180)
 p=compile('run')
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(-5,81));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'SetCapacityDriver',*map(str,vals)],capture_output=True,text=True,check=True,timeout=30);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout,native.stdout,native.stderr))
 p=compile('big')
 if p.returncode:raise RuntimeError(p.stderr)
 native=subprocess.run([str(d/'native'),'0','0'],capture_output=True,text=True,timeout=30)
 if native.returncode==0 or 'capacidad experimental excedida' not in native.stderr:raise AssertionError(('capacity guard',native.stderr))
 print(f'OK: {len(vals)} resultados LinkedHashSet(int) con orden String/null y capacidad negativa; límite experimental explícito')
