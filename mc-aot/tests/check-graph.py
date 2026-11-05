#!/usr/bin/env python3
"""Comprueba aristas Class del grafo Rust frente al pool constante de javap."""
import csv,gzip,os,pathlib,re,subprocess
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';jar=root.parent/'downloads/server-26.3-inner.jar'
classes=['net/minecraft/server/Main','net/minecraft/util/Mth','net/minecraft/util/LightCoordsUtil','net/minecraft/world/flag/FeatureFlagUniverse','net/minecraft/world/level/LevelHeightAccessor$1','net/minecraft/world/level/levelgen/BelowZeroRetrogen$1','net/minecraft/network/protocol/game/ClientboundLoginPacket']
edges={c:set() for c in classes}
with gzip.open(root.parent/'analysis/class-dependencies.tsv.gz','rt') as f:
 for r in csv.DictReader(f,delimiter='\t'):
  if r['clase'] in edges:edges[r['clase']].add(r['dependencia'])
count=0
for cls in classes:
 out=subprocess.run([str(jdk/'javap'),'-verbose','-classpath',str(jar),cls.replace('/','.')],capture_output=True,text=True,check=True).stdout
 refs=set()
 for value in re.findall(r'^\s*#\d+ = Class\s+#\d+\s+//\s+(.*)$',out,re.M):
  value=value.strip('"')
  if value.startswith('['):
   obj=re.fullmatch(r'\[+L(.+);',value)
   if obj:refs.add(obj.group(1))
  else:refs.add(value)
 refs.discard(cls)
 missing=refs-edges[cls]
 if missing:raise AssertionError((cls,sorted(missing)))
 count+=len(refs)
print(f'OK: {count} referencias Class de {len(classes)} clases de javap están en el grafo Rust')
