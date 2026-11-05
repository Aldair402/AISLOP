#!/usr/bin/env python3
"""La evidencia parcial no se convierte en certificación y rechaza inconsistencias."""
import copy,json,os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[2]
tool=root/'mc-aot/tools/class-surface-evidence.py';manifest=root/'analysis/class-evidence/quartpos.json';original=json.loads(manifest.read_text())
def run(path):return subprocess.run(['python3',str(tool),str(path)],capture_output=True,text=True,timeout=180)
p=run(manifest)
if p.returncode:raise RuntimeError(p.stderr)
r=json.loads(p.stdout)
# El manifiesto declara evidencia para `<init>` (medición de reflexión en Java), así que no
# queda ningún miembro sin evidencia declarada. Pero "declarada" no es "diferencial": el
# informe tiene que separar los cinco miembros con diferencial del constructor que solo se
# midió en la JVM, y ese constructor tiene que venir con motivo de inalcanzabilidad. Si el
# informe borra esa distinción, la etapa falla — antes se perdía en silencio (fue el rojo de
# `main` 8d21505, cazado por A; ver Q-AC-5 en analysis/discussion/threads/a-c.md).
if (r['classes_in_jar'],r['methods_declared'],r['methods_with_partial_evidence'],r['fields_declared'],r['fields_with_partial_evidence'],r['certified'],r['methods_without_evidence'])!=(7762,6,6,4,4,False,[]):raise AssertionError(r)
classification=r.get('evidence_classification') or {}
differential=sorted(classification.get('differential',[]))
java_only=sorted(classification.get('java_only',[]))
if differential!=sorted(['fromBlock(I)I','quartLocal(I)I','toBlock(I)I','fromSection(I)I','toSection(I)I','BITS:I','SIZE:I','MASK:I','SECTION_TO_QUARTS_BITS:I']):raise AssertionError(('diferencial',differential))
if java_only!=['<init>()V']:raise AssertionError(('solo-java',java_only))
if classification.get('unclassified_methods') or classification.get('unclassified_fields'):raise AssertionError(('miembros sin clasificar',classification))
# El motivo de inalcanzabilidad vive en el informe, junto a la clasificación.
report=json.loads((root/'analysis/quartpos-evidence-report.json').read_text())
unreachable={u['member']:u.get('reason','') for u in report.get('unreachable_java_only',[])}
if not unreachable.get('<init>()V','').strip():raise AssertionError(('constructor sin motivo de inalcanzabilidad',unreachable))
if report.get('methods_differential')!=5 or report.get('methods_java_only')!=1:raise AssertionError(('recuento diferencial/solo-java',report.get('methods_differential'),report.get('methods_java_only')))
for member in ('differential_members','java_only_members'):
 if not report.get(member):raise AssertionError(('el informe no distingue',member))
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
 print('OK: QuartPos inventariado 6/6 métodos y 4/4 campos con evidencia parcial declarada; 5 miembros con diferencial + el constructor privado marcado solo-Java e inalcanzable con motivo; ocho alteraciones del manifiesto rechazadas; no certifica clases')
