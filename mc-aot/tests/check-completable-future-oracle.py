#!/usr/bin/env python3
"""Semántica Java usada en Main/Util: oráculo preparatorio, sin backend nativo."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
expected='''normal|null|identity|complete-once
exception|join-completion|get-execution|same-cause
cancel|join-direct|get-direct
allOf|wait-all|same-cause|empty-null
callbacks|completer-thread|explicit-executor|rejection-cause
timeout|pending
interrupt|get-throws-cleared|join-returns-preserved
'''
with tempfile.TemporaryDirectory(prefix='mc-completablefuture-oracle-') as t:
 subprocess.run([str(jdk/'javac'),'-d',t,str(root/'tests/CompletableFutureOracle.java')],check=True,capture_output=True,timeout=60)
 for i in range(20):
  result=subprocess.run([str(jdk/'java'),'-cp',t,'CompletableFutureOracle'],capture_output=True,text=True,timeout=20)
  if result.returncode or result.stdout!=expected:raise AssertionError((i,result.returncode,result.stdout,result.stderr))
 print('OK: 20 rondas Java 25: future null/identidad, complete, get/join excepcional, cancelación, allOf, callbacks, timeout e interrupción; SIN implementación ni comparación nativa')
