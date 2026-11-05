#!/usr/bin/env python3
"""Contrasta descriptores extraídos por Rust con javap para clases reales del JAR."""
import collections,os,pathlib,re,subprocess
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root.parent/'downloads/server-26.3-inner.jar'
classes=['net/minecraft/server/Main','net/minecraft/util/Mth','net/minecraft/util/LightCoordsUtil','net/minecraft/world/flag/FeatureFlagUniverse','net/minecraft/world/level/LevelHeightAccessor$1','net/minecraft/world/level/levelgen/BelowZeroRetrogen$1','net/minecraft/network/protocol/game/ClientboundLoginPacket']
count=0
for cls in classes:
 j=subprocess.run([str(jdk/'javap'),'-s','-p','-classpath',str(jar),cls.replace('/','.')],capture_output=True,text=True,check=True).stdout
 java=collections.Counter(re.findall(r'^\s*descriptor:\s*(\S+)',j,re.M))
 rust=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','inspect',str(jar),cls],capture_output=True,text=True,check=True).stdout
 found=[]
 for line in rust.splitlines():
  if not re.match(r'^  0x[0-9a-f]{4} ',line):continue
  part=line.split(' | ',1)[0]
  if '(' in part:desc=part[part.index('('):]
  else:desc=part.rsplit(' ',1)[-1]
  found.append(desc)
 actual=collections.Counter(found)
 if actual!=java:raise AssertionError((cls,java-actual,actual-java))
 count+=len(found)
print(f'OK: {count} descriptores en {len(classes)} clases reales coinciden con javap de Java 25')
