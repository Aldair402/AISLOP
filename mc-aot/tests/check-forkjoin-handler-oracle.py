#!/usr/bin/env python3
"""Oráculo Java de handler, submit y supplyAsync; no compara backend nativo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
expected='''execute|handler|misma-excepcion
submit|join-excepcion|get-executionexception|sin-handler
supplyAsync|causa-identica|sin-handler
shutdown|terminacion|rechazo
'''
with tempfile.TemporaryDirectory(prefix='mc-fjp-handler-oracle-') as d:
 subprocess.run([str(jdk/'javac'),'-d',d,str(root/'tests/ForkJoinHandlerOracle.java')],capture_output=True,text=True,check=True,timeout=60)
 for n in range(20):
  p=subprocess.run([str(jdk/'java'),'-cp',d,'ForkJoinHandlerOracle'],capture_output=True,text=True,timeout=20)
  if p.returncode or p.stdout!=expected:raise AssertionError((n,p.returncode,p.stdout,p.stderr))
 print('OK: 20 rondas Java 25: handler recibe excepción de execute; submit y supplyAsync conservan fallo sin invocarlo; shutdown/terminación/rechazo. Sin backend nativo ni pruebas de excepciones generales.')
