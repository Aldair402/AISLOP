#!/usr/bin/env python3
"""Metafactory sin capturas: despacho, tipos y guardas diferenciales Java 25."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
source='''package net.minecraft.test;import java.util.function.*;
interface Op{int apply(int x);} interface Text{int size();} final class Box implements Text{final int size;Box(String s){size=s.length();}int get(){return size;}public int size(){return size;}static int square(int x){return x*x;}}
public class LambdaDemo{
 static IntUnaryOperator op(){return x->x+3;}
 static Function<String,String> str(){return x->x.trim();}
 static Op project(){return Box::square;}
 public static int run(int n){switch(n%16){case 0:return op().applyAsInt(n);case 1:return op()==op()?1:0;case 2:return str().apply("  hi  ").length();case 3:return project().apply(n);case 4:return project() instanceof Op?1:0;case 5:try{Function f=str();f.apply(Integer.valueOf(4));return 2;}catch(ClassCastException e){return 3;}case 6:return captured(n);case 7:return ((Function<String,Box>)Box::new).apply("hola").get();case 8:return ((Function<Byte,Integer>)LambdaDemo::byteTransform).apply(Byte.valueOf((byte)n)).intValue();case 9:try{return ((Function<Integer,Integer>)LambdaDemo::increment).apply(null).intValue();}catch(NullPointerException e){return 9;}case 10:return ((Function<String,String>)String::trim).apply(" a ").length();case 11:return ((java.util.function.ToIntFunction<Box>)Box::get).applyAsInt(new Box("hello"));case 12:return ((java.util.function.ToIntFunction<Text>)Text::size).applyAsInt(new Box("hey"));case 13:return ((Function<Float,Byte>)LambdaDemo::pack).apply(Float.valueOf((float)n)).byteValue();case 14:return (int)((Function<Byte,Float>)LambdaDemo::unpack).apply(Byte.valueOf((byte)n)).floatValue();default:return op() instanceof IntUnaryOperator?1:0;}}
 static byte pack(float x){return (byte)x;}static float unpack(byte x){return x*2.0f;}
 static int byteTransform(byte n){return n*3;} static int increment(int n){return n+1;}
 public static int captured(int n){return ((IntUnaryOperator)(x->x+n)).applyAsInt(4);}
 public static int methodRef(String s){return ((Function<String,String>)String::toUpperCase).apply(s).length();}
}'''
driver='''import net.minecraft.test.LambdaDemo;public class LambdaDriver{public static void main(String[]a){for(String s:a)System.out.println(LambdaDemo.run(Integer.parseInt(s)));}}'''
with tempfile.TemporaryDirectory(prefix='mc-lambda-') as t:
 d=pathlib.Path(t);(d/'LambdaDemo.java').write_text(source);(d/'LambdaDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'LambdaDemo.java'),str(d/'LambdaDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 base=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/LambdaDemo']
 p=subprocess.run(base+[str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 vals=list(range(140));java=subprocess.run([str(jdk/'java'),'-cp',str(d),'LambdaDriver',*map(str,vals)],capture_output=True,text=True,check=True).stdout
 native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],capture_output=True,text=True,check=True).stdout
 if java!=native:raise AssertionError((java,native))
 p=subprocess.run(base+[str(d/'capture'),'methodRef','(Ljava/lang/String;)I'],capture_output=True,text=True)
 if p.returncode==0 or 'lambda método JDK no soportado' not in p.stderr:raise AssertionError((p.returncode,p.stderr))
 print('OK: 140 operaciones de lambdas con y sin capturas, constructores, métodos virtuales, boxing/unboxing y guardas')
