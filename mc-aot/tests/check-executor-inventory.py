#!/usr/bin/env python3
"""Comprueba conteo y fallo cerrado del inventario, no la semántica de ejecuciones."""
import csv,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin';tool=root/'tools/inspect-executor-calls.py'
source='''import java.util.concurrent.*;
public class InvInventory {
 static void submit(Executor e) { e.execute(() -> {}); }
 static CompletableFuture<String> done(String s) { return CompletableFuture.completedFuture(s).thenApply(x -> x + "!"); }
}'''
with tempfile.TemporaryDirectory(prefix='mc-executor-audit-') as t:
 d=pathlib.Path(t);java=d/'InvInventory.java';java.write_text(source)
 subprocess.run([str(jdk/'javac'),'-d',str(d),str(java)],check=True,capture_output=True,timeout=30)
 jar=d/'in.jar';out=d/'calls.tsv'
 with zipfile.ZipFile(jar,'w') as z:z.write(d/'InvInventory.class','InvInventory.class')
 p=subprocess.run(['python3',str(tool),str(jar),str(out)],capture_output=True,text=True,timeout=30)
 if p.returncode:raise AssertionError((p.stdout,p.stderr))
 rows=list(csv.DictReader(out.open(),delimiter='\t'))
 if len(rows)!=3:raise AssertionError(rows)
 found={(r['metodo'],r['owner'],r['callee']):r for r in rows}
 for k in [('submit','java/util/concurrent/Executor','execute'),('done','java/util/concurrent/CompletableFuture','completedFuture'),('done','java/util/concurrent/CompletableFuture','thenApply')]:
  if k not in found or int(found[k]['invokedynamic_en_metodo'])<1:raise AssertionError(found)
 bad=d/'bad.jar'
 with zipfile.ZipFile(bad,'w') as z:z.writestr('Broken.class',b'not a class')
 p=subprocess.run(['python3',str(tool),str(bad),str(d/'bad.tsv')],capture_output=True,text=True,timeout=30)
 if p.returncode==0 or 'ERRORES DE INVENTARIO' not in p.stderr or (d/'bad.tsv').exists():raise AssertionError((p.returncode,p.stdout,p.stderr))
print('OK: 3 llamadas en bytecode sintético inventariadas; invokedynamic contado por método; classfile inválido rechazado; no demuestra rutas ejecutadas')
