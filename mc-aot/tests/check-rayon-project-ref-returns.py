#!/usr/bin/env python3
"""B-10: métodos de clase del proyecto que DEVUELVEN una referencia y
constructores con firma mixta `(ILnet/minecraft/...;)V`, bajo
`MC_AOT_RAYON_PROJECT_REFERENCES=1`. El retorno comprueba la clase exacta (o
null); los argumentos siguen siendo `I` y referencias del proyecto. Sin el
opt-in se mantiene el rechazo, y una firma no admitida sigue rechazándose."""
import os, pathlib, subprocess, tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'

# `step()`/`self()`/`pick()` devuelven referencias; el constructor de `Node` usa
# una firma mixta `(ILnet/minecraft/test/Node;)V`.
source = '''package net.minecraft.test;
final class Node {
 int value;
 final Node next;
 Node(Node n){next=n;}
 Node(int v,Node n){value=v;next=n;}
 Node step(){return next;}
 Node self(){return this;}
 Node pick(int k,Node alt){if(k==0){return alt;}return next;}
 int read(){return value;}
}
public class RefReturnFixture {
 public static int run(int n){
  Node tail=new Node(13,null);
  Node mid=new Node(11,tail);
  Node head=new Node(7,mid);
  Node probe=head.step().step();
  Node same=head.self();
  Node chosen=head.pick(n,tail);
  return probe.read()+same.read()+chosen.read()+n;
 }
}
'''

# Guarda de firma: `(Ljava/lang/String;)I` no está en el perfil y sigue rechazándose.
guard_source = '''package net.minecraft.test;
final class Wide {
 int value;
 Wide(int v){value=v;}
 int tag(String text){return value;}
}
public class RefReturnFixture {
 public static int run(int n){
  Wide w=new Wide(n);
  return w.tag("x");
 }
}
'''

driver = '''import net.minecraft.test.RefReturnFixture;
public class Driver {public static void main(String[] a){for(String x:a)System.out.println(RefReturnFixture.run(Integer.parseInt(x)));}}'''


def run(cmd, **kw):
    kw.setdefault('timeout', 240)
    return subprocess.run(cmd, text=True, **kw)


def ok(p):
    if p.returncode:
        raise RuntimeError((p.args, p.returncode, p.stdout, p.stderr))
    return p


def build(d, texto, etiqueta, inner):
    c = d / etiqueta
    c.mkdir()
    (c / 'RefReturnFixture.java').write_text(texto)
    (c / 'Driver.java').write_text(driver)
    ok(run([str(jdk / 'javac'), '-cp', str(inner), '-d', str(c),
            str(c / 'RefReturnFixture.java'), str(c / 'Driver.java')], capture_output=True))
    jar = c / 'fixture.jar'
    ok(run([str(jdk / 'jar'), 'cf', str(jar), '-C', str(c), 'net'], capture_output=True))
    return c, jar


with tempfile.TemporaryDirectory(prefix='mc-rayon-refreturn-') as t:
    d = pathlib.Path(t)
    inner = root.parent / 'downloads/server-26.3-inner.jar'

    env = os.environ.copy()
    env['MC_AOT_RAYON_PROJECT_REFERENCES'] = '1'
    nativo_env = env.copy()
    nativo_env['PATH'] = '/nonexistent'
    nativo_env.pop('JAVA_HOME', None)

    def compilar(jar, salida, extra=None):
        return run(['cargo', 'run', '--quiet', '--manifest-path', str(root / 'Cargo.toml'), '--',
                    'concurrent-rayon-int-demo', str(jar), 'net/minecraft/test/RefReturnFixture',
                    str(salida), 'run', '(I)I'], capture_output=True,
                   env=env if extra is None else extra)

    valores = [0, 1, 2, 3, 5, 10, 13, 21] * 4
    c, jar = build(d, source, 'retornos', inner)
    ok(compilar(jar, c / 'native'))
    java = ok(run([str(jdk / 'java'), '-cp', str(c), 'Driver', *map(str, valores)], capture_output=True))
    nativo = ok(run([str(c / 'native'), *map(str, valores)], capture_output=True, env=nativo_env))
    if java.stdout != nativo.stdout:
        raise AssertionError((java.stdout[:400], nativo.stdout[:400], nativo.stderr[:400]))
    total = len(valores)

    # Sin el opt-in no hay referencias de proyecto: nada de retornos por accidente.
    sin_proyecto = env.copy()
    sin_proyecto.pop('MC_AOT_RAYON_PROJECT_REFERENCES')
    rechazo = compilar(jar, c / 'rechazado', sin_proyecto)
    if rechazo.returncode == 0 or (c / 'rechazado').exists():
        raise AssertionError(('sin-referencias-proyecto', rechazo.returncode, rechazo.stderr[:400]))

    # La guarda de firma sigue viva con el opt-in puesto: `(D)I` no está en el perfil.
    c_g, jar_g = build(d, guard_source, 'firma-rechazada', inner)
    firma = compilar(jar_g, c_g / 'native')
    if firma.returncode == 0 or 'firma no soportada: (Ljava/lang/String;)I' not in firma.stderr \
            or (c_g / 'native').exists():
        raise AssertionError(('firma', firma.returncode, firma.stderr[:400]))

    print(f'OK: {total} resultados Java 25/Rayon con métodos del proyecto que devuelven referencia, '
          f'constructores de firma mixta (int + referencia) y lectura encadenada, comprobando la clase exacta '
          f'del retorno; más dos guardas (sin MC_AOT_RAYON_PROJECT_REFERENCES se rechaza, y una firma fuera del '
          f'perfil sigue dando "firma no soportada"); sin reclamo de modelo de memoria, solo valores')
