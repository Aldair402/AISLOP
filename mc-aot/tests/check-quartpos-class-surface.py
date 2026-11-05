#!/usr/bin/env python3
"""Cinco métodos estáticos y cuatro campos reales de QuartPos, no certificación de clase."""
import os,pathlib,random,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root.parent/'downloads/server-26.3-inner.jar'
driver='''import net.minecraft.core.QuartPos;import java.lang.reflect.*;
public class QuartSurface {public static void main(String[] a)throws Exception {for(int i=0;i<a.length;){int op=Integer.parseInt(a[i++]);if(op>=5){String[] names={"BITS","SIZE","MASK","SECTION_TO_QUARTS_BITS"};Field f=QuartPos.class.getDeclaredField(names[op-5]);f.setAccessible(true);System.out.println(f.getInt(null));continue;}int x=Integer.parseInt(a[i++]);System.out.println(switch(op){case 0->QuartPos.fromBlock(x);case 1->QuartPos.quartLocal(x);case 2->QuartPos.toBlock(x);case 3->QuartPos.fromSection(x);case 4->QuartPos.toSection(x);default->throw new AssertionError();});}}}'''
with tempfile.TemporaryDirectory(prefix='mc-quart-surface-') as tmp:
 d=pathlib.Path(tmp);(d/'QuartSurface.java').write_text(driver)
 subprocess.run([str(jdk/'javac'),'-cp',str(jar),'-d',str(d),str(d/'QuartSurface.java')],check=True)
 specs=[('fromBlock','(I)I'),('quartLocal','(I)I'),('toBlock','(I)I'),('fromSection','(I)I'),('toSection','(I)I'),('@BITS','I'),('@SIZE','I'),('@MASK','I'),('@SECTION_TO_QUARTS_BITS','I')]
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(jar),'net/minecraft/core/QuartPos',str(d/'native')]
 for name,desc in specs:cmd.extend((name,desc))
 p=subprocess.run(cmd,text=True,capture_output=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 rng=random.Random(263);values=[-2147483648,-2147483647,-5,-4,-3,-2,-1,0,1,2,3,4,5,2147483646,2147483647]+[rng.randint(-2147483648,2147483647) for _ in range(500)]
 args=[str(i) for i in range(5,9)]
 for n in values:
  for op in range(5):args.extend((str(op),str(n)))
 java=subprocess.run([str(jdk/'java'),'-cp',str(d)+os.pathsep+str(jar),'QuartSurface',*args],text=True,capture_output=True,check=True,timeout=30)
 native=subprocess.run([str(d/'native'),*args],text=True,capture_output=True,timeout=30)
 if native.returncode or java.stdout!=native.stdout:raise AssertionError((java.stdout[:500],native.stdout[:500],native.stderr))
 print(f'OK: {len(values)*5+4} resultados, cinco métodos y cuatro campos declarados de QuartPos oficial; no prueba constructor privado, reflexión general ni clase completa')
