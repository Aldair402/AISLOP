#!/usr/bin/env python3
"""La evidencia parcial no se convierte en certificación y rechaza inconsistencias."""
import copy,json,os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[2]
tool=root/'mc-aot/tools/class-surface-evidence.py';manifest=root/'analysis/class-evidence/quartpos.json';original=json.loads(manifest.read_text())
def run(path):return subprocess.run(['python3',str(tool),str(path)],capture_output=True,text=True,timeout=180)
p=run(manifest)
if p.returncode:raise RuntimeError(p.stderr)
r=json.loads(p.stdout)
# El manifiesto ya declara evidencia para `<init>` (la medición de reflexión en Java del
# constructor privado), así que la superficie queda sin miembros sin evidencia declarada.
# Ojo: el inventario NO distingue evidencia diferencial de evidencia solo-Java; por eso
# `certified` sigue en False y el conteo de clases no puede salir de este archivo
# (ver Q-AC-5 en analysis/discussion/threads/a-c.md).
if (r['classes_in_jar'],r['methods_declared'],r['methods_with_partial_evidence'],r['fields_declared'],r['fields_with_partial_evidence'],r['certified'],r['methods_without_evidence'])!=(7762,6,6,4,4,False,[]):raise AssertionError(r)
with tempfile.TemporaryDirectory(prefix='mc-evidence-guard-') as t:
 d=pathlib.Path(t)
 def reject(label,mutate,expected):
  m=copy.deepcopy(original);mutate(m);p=d/(label+'.json');p.write_text(json.dumps(m));r=run(p)
  if r.returncode==0 or expected not in r.stderr:raise AssertionError((label,r.returncode,r.stderr))
 reject('jar',lambda m:m.update(jar_sha256='0'*64),'hash de JAR no coincide')
 reject('class',lambda m:m.update(class_sha256='0'*64),'hash de clase no coincide')
 reject('file',lambda m:m['members'][0]['evidence'][0].update(sha256='0'*64),'hash de evidencia no coincide')
 reject('escape',lambda m:m['members'][0]['evidence'][0].update(path='/etc/passwd'),'fuera del workspace')
 reject('missing',lambda m:m['members'][0]['evidence'][0].update(path='analysis/no-existe-evidencia'),'ausente')
 reject('duplicate',lambda m:m['members'].append(copy.deepcopy(m['members'][0])),'duplicado en manifiesto')
 reject('unknown',lambda m:m['members'][0].update(name='inexistente'),'miembro no declarado')
 reject('certify',lambda m:m.update(certified=True),'no se permiten afirmaciones de certificación')
 print('OK: QuartPos inventariado 6/6 métodos y 4/4 campos con evidencia parcial declarada (incluye el constructor privado, medido solo en Java); ocho alteraciones rechazadas; no certifica clases ni distingue evidencia diferencial de solo-Java')
