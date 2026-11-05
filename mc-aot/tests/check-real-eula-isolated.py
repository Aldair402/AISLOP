#!/usr/bin/env python3
"""Código Eula.class oficial con dependencias simuladas; NO prueba el servidor."""
import os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
sources={
 'net/minecraft/SharedConstants.java':'package net.minecraft;public class SharedConstants{public static boolean IS_RUNNING_IN_IDE;}',
 'net/minecraft/util/CommonLinks.java':'package net.minecraft.util;public class CommonLinks{public static java.net.URI EULA=java.net.URI.create("https://aka.ms/MinecraftEULA");}',
 'org/slf4j/Logger.java':'package org.slf4j;public interface Logger{void warn(String a,Object b);void warn(String a,Object b,Object c);}',
 'com/mojang/logging/LogUtils.java':'package com.mojang.logging;import org.slf4j.Logger;public class LogUtils{public static Logger getLogger(){return new N();}static class N implements Logger{public void warn(String a,Object b){}public void warn(String a,Object b,Object c){}}}',
 'net/minecraft/test/EulaProbe.java':'package net.minecraft.test;import java.nio.file.*;import net.minecraft.server.Eula;public class EulaProbe{public static int run(int n){return new Eula(Path.of("eula"+n+".txt")).hasAgreedToEULA()?1:0;}}',
 'EDriver.java':'import net.minecraft.test.EulaProbe;public class EDriver{public static void main(String[]a){for(String x:a)System.out.println(EulaProbe.run(Integer.parseInt(x)));}}'
}
with tempfile.TemporaryDirectory(prefix='mc-eula-isolated-') as t:
 d=pathlib.Path(t);c=d/'classes';c.mkdir();e=c/'net/minecraft/server/Eula.class';e.parent.mkdir(parents=True)
 with zipfile.ZipFile(root.parent/'downloads/server-26.3-inner.jar') as z:e.write_bytes(z.read('net/minecraft/server/Eula.class'))
 paths=[]
 for name,text in sources.items():p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);paths.append(str(p))
 subprocess.run([str(jdk/'javac'),'-cp',str(c),'-d',str(c),*paths],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(c),'.'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/EulaProbe',str(d/'native'),'run','(I)I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 for i,val in enumerate(['true','false','TrUe']):(d/f'eula{i}.txt').write_text('eula='+val+'\n')
 vals=[i%3 for i in range(120)];j=subprocess.run([str(jdk/'java'),'-cp',str(c),'EDriver',*map(str,vals)],cwd=d,capture_output=True,text=True,check=True);a=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))]],cwd=d,capture_output=True,text=True)
 if a.returncode or j.stdout!=a.stdout:raise AssertionError((a.returncode,j.stdout,a.stdout,a.stderr))
 env={**os.environ,'TZ':'UTC','MC_AOT_JAVA_TIMEZONE':'UTC'}
 jmissing=subprocess.run([str(jdk/'java'),'-Duser.timezone=UTC','-cp',str(c),'EDriver','9'],cwd=d,capture_output=True,text=True,env=env,check=True)
 original=(d/'eula9.txt').read_text().splitlines();(d/'eula9.txt').unlink()
 nmissing=subprocess.run([str(d/'native'),'0','9'],cwd=d,capture_output=True,text=True,env=env)
 if nmissing.returncode or nmissing.stdout!=jmissing.stdout:raise AssertionError((nmissing.returncode,nmissing.stdout,nmissing.stderr,jmissing.stdout))
 generated=(d/'eula9.txt').read_text().splitlines()
 if len(original)!=3 or len(generated)!=3 or original[0]!=generated[0] or original[2]!=generated[2] or ' UTC ' not in generated[1]:raise AssertionError((original,generated))
 import datetime
 stamp=datetime.datetime.strptime(generated[1],"#%a %b %d %H:%M:%S UTC %Y").replace(tzinfo=datetime.timezone.utc)
 if abs((datetime.datetime.now(datetime.timezone.utc)-stamp).total_seconds())>10:raise AssertionError(generated)
 (d/'eula9.txt').unlink(); unconfigured={k:v for k,v in env.items() if k not in ('TZ','MC_AOT_JAVA_TIMEZONE')};p=subprocess.run([str(d/'native'),'0','9'],cwd=d,capture_output=True,text=True,env=unconfigured)
 if p.returncode==0 or 'requiere MC_AOT_JAVA_TIMEZONE=UTC' not in p.stderr:raise AssertionError((p.returncode,p.stdout,p.stderr))
 print('OK: Eula.class oficial con stubs: 120 decisiones y creación real UTC de eula=false')
