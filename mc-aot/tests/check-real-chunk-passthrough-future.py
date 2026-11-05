#!/usr/bin/env python3
"""ChunkStatusTasks.passThrough oficial con colaboradores y logger sustituidos, no servidor."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
'net/minecraft/world/level/chunk/ChunkAccess.java':'''package net.minecraft.world.level.chunk; public class ChunkAccess { public int n; public ChunkAccess(int n){this.n=n;} }''',
'net/minecraft/world/level/chunk/status/WorldGenContext.java':'''package net.minecraft.world.level.chunk.status; public class WorldGenContext {}''',
'net/minecraft/world/level/chunk/status/ChunkStep.java':'''package net.minecraft.world.level.chunk.status; public class ChunkStep {}''',
'net/minecraft/server/level/GenerationChunkHolder.java':'''package net.minecraft.server.level; public class GenerationChunkHolder {}''',
'net/minecraft/util/StaticCache2D.java':'''package net.minecraft.util; public class StaticCache2D<T> {}''',
'org/slf4j/Logger.java':'''package org.slf4j; public interface Logger {}''',
'com/mojang/logging/LogUtils.java':'''package com.mojang.logging; public class LogUtils { public static org.slf4j.Logger getLogger(){return null;} }''',
'net/minecraft/test/FutureRealProbe.java':'''package net.minecraft.test;
import net.minecraft.world.level.chunk.ChunkAccess;import net.minecraft.world.level.chunk.status.ChunkStatusTasks;import java.util.concurrent.CompletableFuture;
public class FutureRealProbe {public static int run(int n) throws Exception {ChunkAccess chunk=new ChunkAccess(n);CompletableFuture<ChunkAccess> f=ChunkStatusTasks.passThrough(null,null,null,chunk);int result=0;if(f.get()==chunk)result+=1;if(f.join()==chunk)result+=2;if(f.getNow(null)==chunk)result+=4;if(f.isDone())result+=8;if(ChunkStatusTasks.passThrough(null,null,null,null).get()==null)result+=16;return result+chunk.n;}}''',
'Driver.java':'''import net.minecraft.test.FutureRealProbe;public class Driver{public static void main(String[] a)throws Exception{for(String x:a)System.out.println(FutureRealProbe.run(Integer.parseInt(x)));}}'''
}
def run(cmd,**kw):kw.setdefault('timeout',180);return subprocess.run(cmd,text=True,**kw)
def ok(p):
 if p.returncode:raise RuntimeError((p.args,p.returncode,p.stdout,p.stderr))
 return p
with tempfile.TemporaryDirectory(prefix='mc-real-future-') as t:
 d=pathlib.Path(t);inner=root.parent/'downloads/server-26.3-inner.jar';paths=[]
 for name,src in sources.items():p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src);paths.append(str(p))
 ok(run([str(jdk/'javac'),'-cp',str(inner),'-d',str(d),*paths],capture_output=True))
 with zipfile.ZipFile(inner) as z:
  name='net/minecraft/world/level/chunk/status/ChunkStatusTasks.class';b=z.read(name);assert hashlib.sha256(b).hexdigest()=='7fe59213bcd885d715828094a7a7b02458721769360468af2da1bd23edbaaa93';p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 # Extraer clases oficiales a directorio sin firmas evita mezclar packages firmados
 # con los stubs; sus bytes no se modifican. La clase bajo prueba se hashea arriba.
 classes=d/'official';classes.mkdir()
 with zipfile.ZipFile(inner) as z:
  for info in z.infolist():
   if info.filename.endswith('.class'):
    path=pathlib.PurePosixPath(info.filename)
    if path.is_absolute() or '..' in path.parts:raise ValueError('ruta insegura')
    p=classes/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info))
 ok(run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net','-C',str(d),'com','-C',str(d),'org'],capture_output=True))
 env=os.environ.copy();env['MC_AOT_NUMERIC_COMPLETED_FUTURE']='1'
 cmd=['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FutureRealProbe',str(d/'native'),'run','(I)I']
 ok(run(cmd,capture_output=True,env=env))
 values=[-2147483648,-100,-1,0,1,10,100,2147483647]*10
 java=ok(run([str(jdk/'java'),'-cp',os.pathsep.join([str(d),str(classes)]),'Driver',*map(str,values)],capture_output=True))
 native_env=env.copy();native_env['PATH']='/nonexistent';native_env.pop('JAVA_HOME',None)
 native=ok(run([str(d/'native'),*[v for n in values for v in ('0',str(n))]],capture_output=True,env=native_env))
 assert java.stdout==native.stdout,(java.stdout,native.stdout,native.stderr)
 print(f'OK: {len(values)} resultados Java/nativo para ChunkStatusTasks.passThrough oficial, completedFuture/get/join/getNow e identidad/null; classfile hash verificado; ChunkAccess, logger y otros colaboradores son stubs, sin integración de mundo')
