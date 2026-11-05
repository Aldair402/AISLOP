#!/usr/bin/env python3
"""Referencias directas en bytecode; no encuentra todos los usos por interfaces/reflexión."""
import collections,pathlib,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from scan_bytecode import parse,instructions,resolve
jar=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else root.parent/'downloads/server-26.3-inner.jar'
found=[]
with zipfile.ZipFile(jar) as z:
 for file in z.namelist():
  if not file.endswith('.class'):continue
  cp,methods=parse(z.read(file))
  for _,name,desc,code in methods:
   for offset,opcode,data in instructions(code):
    if opcode not in (0xb6,0xb7,0xb8,0xb9):continue
    ref=resolve(cp,int.from_bytes(data[:2],'big'))
    if ref and ref[0].startswith('java/util/concurrent/ForkJoin'):
     found.append((file[:-6],name,desc,str(offset),*ref))
print('clase\tmétodo\tdescriptor\toffset\towner\tcallee\tdescriptor_destino')
for row in sorted(found):print('\t'.join(row))
print(f'{len(found)} referencias directas; no incluye llamadas por ExecutorService ni reflexión',file=sys.stderr)
