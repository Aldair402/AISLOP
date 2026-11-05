#!/usr/bin/env python3
"""Inventario + compilación real de todos los métodos static con argumentos int y retorno int/boolean/byte/char/short de 26.3.
No prueba equivalencia, inicialización de clase ni clases completas.
"""
import collections
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
JAR = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT.parent/'downloads/server-26.3-inner.jar'
REPORT = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT.parent/'analysis/audit-static-primitives.json'
if not JAR.is_file(): raise SystemExit(f'JAR no encontrado: {JAR}')
subprocess.run(['cargo','build','--release','--manifest-path',str(ROOT/'Cargo.toml')],check=True)
binary = ROOT/'target/release/mc-aot'
if not binary.is_file(): raise SystemExit('No se encontró el ejecutable de mc-aot en target/release')
with tempfile.TemporaryDirectory(prefix='mc-audit-') as temp:
    d = pathlib.Path(temp); manifest=d/'methods.tsv'
    scan=subprocess.run([sys.executable,str(ROOT/'scan-bytecode.py'),str(JAR),str(manifest)], text=True,capture_output=True,check=True)
    inventory=json.loads(scan.stdout)
    if inventory['parse_failures']: raise SystemExit(f"Inventario incompleto: {len(inventory['parse_failures'])} errores de lectura")
    records=[]
    for line in manifest.read_text().splitlines():
        cls, method, desc=line.split('\t');records.append((cls,method,desc))
    def audit(item):
        number,(cls,method,desc)=item
        output=d/f'method-{number}'
        cmd=[str(binary),'compile',str(JAR),cls,method,desc,str(output)]
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
            result={'class':cls,'method':method,'descriptor':desc,'compiled':p.returncode==0}
            if p.returncode!=0:
                result['error']=(p.stderr.strip() or p.stdout.strip() or f'code {p.returncode}')[:700]
            return result
        except subprocess.TimeoutExpired:
            return {'class':cls,'method':method,'descriptor':desc,'compiled':False,'error':'timeout tras 45 segundos'}
        finally:
            output.unlink(missing_ok=True)
            pathlib.Path(str(output)+'.rs').unlink(missing_ok=True)
    # Dos trabajos mantienen moderado el uso de CPU y memoria.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(audit,enumerate(records)))
    successful=[r for r in results if r['compiled']]
    classes=sorted({r['class'] for r in successful})
    report={
      'jar':str(JAR), 'classes_in_jar':inventory['classes'],
      'methods_with_code_in_jar':inventory['methods_with_code'],
      'scope':'Métodos estáticos con cero o más parámetros int y retorno int, boolean, byte, char o short; no se consideran otros métodos.',
      'candidate_methods':len(records), 'candidate_classes':inventory['classes_with_static_primitive_return_methods'],
      'compiled_methods':len(successful), 'classes_with_at_least_one_compiled_method':len(classes),
      'compiled_int_return_methods':sum(r['compiled'] and r['descriptor'].endswith(')I') for r in results),
      'compiled_narrow_return_methods':sum(r['compiled'] and not r['descriptor'].endswith(')I') for r in results),
      'fully_supported_classes_certified':0,
      'results':results,
      'limitations':'Compilación Rust exitosa ≠ equivalencia ni clase completa: no valida resultados, inicializadores, excepciones, métodos excluidos ni el arranque del servidor.',
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(f"JAR: {report['classes_in_jar']} clases; {report['methods_with_code_in_jar']} métodos con código")
    print(f"Alcance (static int y retornos primitivos pequeños): {report['candidate_methods']} métodos en {report['candidate_classes']} clases")
    print(f"Compilan: {report['compiled_methods']} métodos en {report['classes_with_at_least_one_compiled_method']} clases")
    print('Clases completas certificadas: 0; no se evalúa equivalencia ni compatibilidad completa.')
    print(f'Informe: {REPORT}')
