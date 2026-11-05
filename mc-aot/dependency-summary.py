#!/usr/bin/env python3
"""Resumen del grafo estático; no prueba ejecución ni alcanza clases cargadas dinámicamente."""
import collections,csv,gzip,hashlib,io,json,pathlib,re,zipfile
root=pathlib.Path(__file__).resolve().parent.parent
index=root/'analysis/class-index.tsv';edges=root/'analysis/class-dependencies.tsv.gz';bundle=root/'downloads/server-26.3.jar';out=root/'analysis/dependency-summary.json'
with index.open() as f: classes={r['clase'] for r in csv.DictReader(f,delimiter='\t')}
graph=collections.defaultdict(set)
with gzip.open(edges,'rt',encoding='utf-8',newline='') as f:
 for row in csv.DictReader(f,delimiter='\t'):graph[row['clase']].add(row['dependencia'])
libs=set();count=0
with zipfile.ZipFile(bundle) as z:
 for line in z.read('META-INF/libraries.list').decode().splitlines():
  checksum,_,rel=line.split('\t');data=z.read('META-INF/libraries/'+rel)
  if hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('checksum de biblioteca incorrecto: '+rel)
  count+=1
  with zipfile.ZipFile(io.BytesIO(data)) as lib:
   for name in lib.namelist():
    if not name.endswith('.class'):continue
    name=re.sub(r'^META-INF/versions/\d+/', '',name)
    if not name.startswith('META-INF/') and not name.endswith(('module-info.class','package-info.class')):libs.add(name[:-6])
rootclass='net/minecraft/server/Main'
if rootclass not in classes:raise SystemExit('Main no está en el índice')
visited={rootclass};q=collections.deque([rootclass])
while q:
 c=q.popleft()
 for dep in graph.get(c,()):
  if dep in classes and dep not in visited:visited.add(dep);q.append(dep)
refs={dep for c in visited for dep in graph.get(c,())}
missing=collections.Counter(dep for c in visited for dep in graph.get(c,()) if dep not in classes and dep not in libs and not dep.startswith(('java/','javax/','jdk/','sun/','com/sun/')))
category={'minecraft_inner':len(refs & classes),'bundled_libraries':len((refs-classes)&libs),'jdk_like_prefix':len({r for r in refs-classes-libs if r.startswith(('java/','javax/','jdk/','sun/','com/sun/'))}),'other_unresolved':len(missing)}
summary={'root':rootclass,'classes_in_inner_jar':len(classes),'libraries_scanned_and_verified':count,'library_class_names':len(libs),'static_closure_classes_in_inner_jar':len(visited),'unique_references_from_static_closure':len(refs),'reference_categories':category,'most_frequent_other_references':[{'class':name,'referenced_by_classes':n} for name,n in missing.most_common(40)],'limitations':'Cierre del grafo estático a nivel de clase: incluye referencias no ejecutadas y omite reflexión, carga dinámica, detalles de multi-release y recursos; no representa el conjunto real de arranque ni indica soporte. Prefijos JDK no garantizan disponibilidad.'}
out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
