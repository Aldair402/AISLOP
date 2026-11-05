#!/usr/bin/env python3
"""Invocaciones directas a APIs de logging en el JAR interno; no rastrea reflexión ni despacho indirecto."""
import collections,pathlib,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from scan_bytecode import parse,instructions,resolve
jar=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else root.parent/'downloads/server-26.3-inner.jar'
prefixes=('org/slf4j/','org/apache/logging/log4j/','com/mojang/logging/')
found=[]; signatures=collections.Counter();classes=set()
with zipfile.ZipFile(jar) as z:
 for file in z.namelist():
  if not file.endswith('.class'):continue
  cp,methods=parse(z.read(file))
  for _,name,desc,code in methods:
   for offset,opcode,data in instructions(code):
    if opcode not in (0xb6,0xb7,0xb8,0xb9):continue
    ref=resolve(cp,int.from_bytes(data[:2],'big'))
    if ref and ref[0].startswith(prefixes):
     found.append((file[:-6],name,desc,str(offset),*ref));signatures[ref]+=1;classes.add(file[:-6])
print('clase\tmétodo\tdescriptor\toffset\towner\tcallee\tdescriptor_destino')
for row in sorted(found):print('\t'.join(row))
print(f'{len(found)} invocaciones directas en {len(classes)} clases; no incluye despacho indirecto/reflexión',file=sys.stderr)
for (owner,name,desc),count in signatures.most_common():print(f'{count}\t{owner}\t{name}\t{desc}',file=sys.stderr)
