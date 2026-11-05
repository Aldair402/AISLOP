#!/usr/bin/env python3
"""Differential valueOf checks against three unmodified Minecraft 26.3 enum classes."""
import hashlib, os, pathlib, subprocess, tempfile, zipfile
root=pathlib.Path(__file__).resolve().parents[1]; project=root.parent
jdk=pathlib.Path(os.environ.get('JAVA_HOME','/var/tmp/mc-java25'))/'bin'
classes={
 'net/minecraft/network/protocol/PacketFlow.class':'2e56381975ddf20c7054c91cc6476d965339c208d866eb1ce534840156964dee',
 'net/minecraft/world/level/material/PushReaction.class':'ea9f3a50855e584427365f9f5dd209e6f0770c86496e473d2f536c0b8820ce17',
 'net/minecraft/world/level/chunk/status/ChunkType.class':'4cefb97eb9735f9a10e34b419ef401d1fbf985af554d3eb68c6e1a202877dd51',
}
source='''package net.minecraft.test;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.world.level.material.PushReaction;
import net.minecraft.world.level.chunk.status.ChunkType;
public class RealEnumValueOf {
 public static int run(int x){
  int k=(x & 0x7fffffff)%12;
  if(k==0)return PacketFlow.valueOf("SERVERBOUND")==PacketFlow.SERVERBOUND?11:-1;
  if(k==1)return Enum.valueOf(PacketFlow.class,"CLIENTBOUND")==PacketFlow.CLIENTBOUND?12:-1;
  if(k==2)return PushReaction.valueOf("PUSH_PULL")==PushReaction.PUSH_PULL?13:-1;
  if(k==3)return Enum.valueOf(PushReaction.class,"IGNORE_ENTITY")==PushReaction.IGNORE_ENTITY?14:-1;
  if(k==4)return ChunkType.valueOf("PROTOCHUNK")==ChunkType.PROTOCHUNK?15:-1;
  if(k==5)return Enum.valueOf(ChunkType.class,"LEVELCHUNK")==ChunkType.LEVELCHUNK?16:-1;
  if(k==6)return PacketFlow.valueOf("CLIENTBOUND").ordinal();
  if(k==7)return PushReaction.valueOf("POPPED").name().equals("POPPED")?18:-1;
  if(k==8){try{PacketFlow.valueOf("missing");return -1;}catch(IllegalArgumentException e){return e.getMessage().equals("No enum constant net.minecraft.network.protocol.PacketFlow.missing")?19:-1;}}
  if(k==9){try{ChunkType.valueOf("");return -1;}catch(IllegalArgumentException e){return e.getMessage().equals("No enum constant net.minecraft.world.level.chunk.status.ChunkType.")?20:-1;}}
  if(k==10){try{PushReaction.valueOf(null);return -1;}catch(NullPointerException e){return e.getMessage().equals("Name is null")?21:-1;}}
  return PushReaction.valueOf("PUSH")==Enum.valueOf(PushReaction.class,"PUSH")?22:-1;
 }
 public static void main(String[] a){for(int i=0;i<180;i++)System.out.println(run(i));}
}'''
with tempfile.TemporaryDirectory(prefix='mc-real-enum-') as td:
 d=pathlib.Path(td); f=d/'RealEnumValueOf.java'; f.write_text(source)
 official=project/'downloads/server-26.3-inner.jar'
 subprocess.run([str(jdk/'javac'),'-cp',str(official),'-d',str(d),str(f)],check=True)
 with zipfile.ZipFile(official) as z:
  for n,expected in classes.items():
   b=z.read(n); assert hashlib.sha256(b).hexdigest()==expected, n
   out=d/n;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b)
 fixture=d/'fixture.jar'
 subprocess.run([str(jdk/'jar'),'cf',str(fixture),'-C',str(d),'net'],check=True)
 java=subprocess.run([str(jdk/'java'),'-cp',str(fixture),'net.minecraft.test.RealEnumValueOf'],capture_output=True,text=True,check=True,timeout=60).stdout.splitlines()
 assert len(java)==180 and '-1' not in java, java
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(fixture),'net/minecraft/test/RealEnumValueOf',str(d/'native'),'run','(I)I'],capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr)
 native=[]
 for i in range(180):
  p=subprocess.run([str(d/'native'),'0',str(i)],capture_output=True,text=True,timeout=10)
  if p.returncode:raise RuntimeError((i,p.stderr))
  native.append(p.stdout.strip())
 if java!=native:raise AssertionError([(i,a,b) for i,(a,b) in enumerate(zip(java,native)) if a!=b])
 print('OK: 180 resultados Java 25/nativo; valueOf en tres enums Minecraft oficiales y hashes verificados; no certifica clases completas')
