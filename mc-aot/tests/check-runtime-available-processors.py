#!/usr/bin/env python3
"""`Runtime.availableProcessors`: una sola fuente (`MC_AOT_JAVA_PROCESSORS`).

Fija la fuente única de procesadores que A le debe a B para la decisión de `commonPool()`:
un único valor leído una sola vez por ejecución del binario, el mismo para
`Runtime.availableProcessors` y para cualquier pool derivado (criterio acordado en la
discusión del perfil de futuros: nunca una segunda lectura del host).

Comprueba, contra Java 25 y contra el binario nativo:

1. Java 25 con `-XX:ActiveProcessorCount=N` imprime exactamente N (oráculo de la
   semántica "comparable al flag de la JVM"; medido en Temurin 25.0.5+8 para
   N ∈ {1, 2, 7, 64, 255, 1024}).
2. El binario traducido con `MC_AOT_JAVA_PROCESSORS=N` imprime exactamente N para los
   mismos N — es decir, el número que ve `Runtime.availableProcessors()` en A es el
   mismo que fijaría la JVM con el flag, y B puede alimentar `commonPool()` con ese
   único valor sin releer nada.
3. Guardas del binario nativo: sin la variable → aborto con
   «Runtime.availableProcessors: configura MC_AOT_JAVA_PROCESSORS»;
   `0` o negativos → «MC_AOT_JAVA_PROCESSORS debe ser positivo»;
   texto, decimales o desbordamiento de i32 → «MC_AOT_JAVA_PROCESSORS inválido».

Lo que NO demuestra: el número de procesadores del host, ni el comportamiento de la
JVM sin flag (la JVM reporta la máquina, el backend nativo aborta si falta la variable:
es la diferencia declarada del contrato experimental), ni que `commonPool()` exista
(`pool.common-pool` sigue java-only hasta que B lo implemente con este mismo valor).
"""
import os, pathlib, subprocess, tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'

src = 'package net.minecraft.test;public class ProcessorsDemo{public static int run(int n){return Runtime.getRuntime().availableProcessors();}}'
driver = 'import net.minecraft.test.ProcessorsDemo;public class Driver{public static void main(String[]a){for(String x:a)System.out.println(ProcessorsDemo.run(Integer.parseInt(x)));}}'

CASES = (1, 2, 7, 64, 255, 1024)
BAD = (('0', 'debe ser positivo'),
       ('-3', 'debe ser positivo'),
       ('abc', 'inválido'),
       ('2.5', 'inválido'),
       ('9999999999', 'inválido'))


def run(cmd, **kw):
    kw.setdefault('timeout', 180)
    return subprocess.run(cmd, text=True, **kw)


def ok(p, what):
    if p.returncode:
        raise RuntimeError((what, p.args, p.returncode, p.stdout, p.stderr))
    return p


with tempfile.TemporaryDirectory(prefix='mc-runtime-processors-') as t:
    d = pathlib.Path(t)
    (d / 'ProcessorsDemo.java').write_text(src)
    (d / 'Driver.java').write_text(driver)
    ok(run([str(jdk / 'javac'), '-d', str(d), str(d / 'ProcessorsDemo.java'), str(d / 'Driver.java')],
           capture_output=True), 'javac')
    ok(run([str(jdk / 'jar'), 'cf', str(d / 'fixture.jar'), '-C', str(d), 'net'],
           capture_output=True), 'jar')
    p = run(['cargo', 'run', '--quiet', '--manifest-path', str(root / 'Cargo.toml'), '--',
             'multi-static-demo', str(d / 'fixture.jar'),
             'net/minecraft/test/ProcessorsDemo', str(d / 'native'), 'run', '(I)I'],
            capture_output=True)
    ok(p, 'multi-static-demo')

    for n in CASES:
        java = ok(run([str(jdk / 'java'), f'-XX:ActiveProcessorCount={n}', '-cp', str(d),
                       'Driver', str(n)], capture_output=True), f'java N={n}')
        assert java.stdout.strip() == str(n), (java.stdout, n)
        env = os.environ.copy()
        env['MC_AOT_JAVA_PROCESSORS'] = str(n)
        native = ok(run([str(d / 'native'), '0', str(n)], env=env, capture_output=True),
                    f'native N={n}')
        assert native.stdout == java.stdout, (n, java.stdout, native.stdout)
        print(f'OK: N={n} coincide en Java 25 (-XX:ActiveProcessorCount) y en el binario nativo')

    # Sin configuración, el binario aborta (la JVM reportaría la máquina; el contrato nativo no la inventa).
    env = os.environ.copy()
    env.pop('MC_AOT_JAVA_PROCESSORS', None)
    p = run([str(d / 'native'), '0', '0'], env=env, capture_output=True)
    assert p.returncode != 0 and 'Runtime.availableProcessors: configura MC_AOT_JAVA_PROCESSORS' in p.stderr, p.stderr
    print('OK: sin MC_AOT_JAVA_PROCESSORS el binario aborta con el mensaje del contrato')

    for value, marker in BAD:
        env = os.environ.copy()
        env['MC_AOT_JAVA_PROCESSORS'] = value
        p = run([str(d / 'native'), '0', '0'], env=env, capture_output=True)
        assert p.returncode != 0 and marker in p.stderr, (value, p.returncode, p.stderr)
        print(f'OK: {value!r} rechazado con «{marker}»')

print('OK: una única fuente (MC_AOT_JAVA_PROCESSORS), comparable a -XX:ActiveProcessorCount; '
      'guardas de ausencia, signo, formato y rango i32 verificadas')
