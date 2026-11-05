#!/usr/bin/env python3
"""B-09: campos de referencia no `final` en el backend concurrente, bajo
`MC_AOT_RAYON_MUTABLE_REFS=1`. La escritura pasa por el mutex del heap, el destino
debe estar publicado y ser de la clase esperada, y sin el opt-in se mantiene el
rechazo. No reclama el modelo de memoria de Java: compara valores, no orden."""
import hashlib, os, pathlib, subprocess, tempfile, zipfile

root = pathlib.Path(__file__).resolve().parents[1]
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'

# `next` NO es final: se escribe fuera del constructor, en un método synchronized.
source = '''package net.minecraft.test;
final class Node {
 int value;
 Node next;
 Node(int v){value=v;}
 synchronized void link(Node n){next=n;}
 int read(){return value;}
}
public class MutableRefFixture {
 public static int run(int n){
  Node a=new Node(7);Node b=new Node(11);Node c=new Node(13);
  int par=1;
  for(int i=0;i<n;i++){if(par==1){a.link(b);par=0;}else{a.link(c);par=1;}}
  return a.next.read()*10+a.read();
 }
}
'''

# Control: mismo perfil con `next` final (no debe cambiar con el opt-in).
source_final = '''package net.minecraft.test;
final class Node {
 int value;
 final Node next;
 Node(Node n){next=n;}
 int read(){return value;}
}
public class MutableRefFixture {
 public static int run(int n){
  Node tail=new Node(null);tail.value=13;
  Node mid=new Node(tail);mid.value=11;
  Node head=new Node(mid);head.value=7;
  return head.next.read()*10+n+tail.read();
 }
}
'''

driver = '''import net.minecraft.test.MutableRefFixture;
public class Driver {public static void main(String[] a){for(String x:a)System.out.println(MutableRefFixture.run(Integer.parseInt(x)));}}'''


def run(cmd, **kw):
    kw.setdefault('timeout', 240)
    return subprocess.run(cmd, text=True, **kw)


def ok(p):
    if p.returncode:
        raise RuntimeError((p.args, p.returncode, p.stdout, p.stderr))
    return p


def build(d, texto, etiqueta):
    """Compila fixture + driver en `d`, devuelve el nombre del jar."""
    c = d / etiqueta
    c.mkdir()
    (c / 'MutableRefFixture.java').write_text(texto)
    (c / 'Driver.java').write_text(driver)
    ok(run([str(jdk / 'javac'), '-cp', str(inner), '-d', str(c),
            str(c / 'MutableRefFixture.java'), str(c / 'Driver.java')], capture_output=True))
    jar = c / 'fixture.jar'
    ok(run([str(jdk / 'jar'), 'cf', str(jar), '-C', str(c), 'net'], capture_output=True))
    return c, jar


with tempfile.TemporaryDirectory(prefix='mc-rayon-mutable-') as t:
    d = pathlib.Path(t)
    inner = root.parent / 'downloads/server-26.3-inner.jar'

    env = os.environ.copy()
    env['MC_AOT_RAYON_PROJECT_REFERENCES'] = '1'
    env['MC_AOT_RAYON_MUTABLE_REFS'] = '1'
    nativo_env = env.copy()
    nativo_env['PATH'] = '/nonexistent'
    nativo_env.pop('JAVA_HOME', None)

    def compilar(jar, salida, etiqueta_env=None):
        return run(['cargo', 'run', '--quiet', '--manifest-path', str(root / 'Cargo.toml'), '--',
                    'concurrent-rayon-int-demo', str(jar), 'net/minecraft/test/MutableRefFixture',
                    str(salida), 'run', '(I)I'], capture_output=True,
                   env=etiqueta_env if etiqueta_env is not None else env)

    valores = [1, 2, 3, 10, 101, 1000, 7] * 4
    total = 0
    for etiqueta, texto in (('mutable', source), ('final', source_final)):
        c, jar = build(d, texto, etiqueta)
        ok(compilar(jar, c / 'native'))
        java = ok(run([str(jdk / 'java'), '-cp', str(c), 'Driver', *map(str, valores)], capture_output=True))
        nativo = ok(run([str(c / 'native'), *map(str, valores)], capture_output=True, env=nativo_env))
        if java.stdout != nativo.stdout:
            raise AssertionError((etiqueta, java.stdout[:200], nativo.stdout[:200], nativo.stderr[:400]))
        total += len(valores)

    # Sin el opt-in se mantiene el rechazo: nada de referencias mutables por accidente.
    c_mutable, jar_mutable = build(d, source, 'mutable-rechazo')
    sin_optin = env.copy()
    sin_optin.pop('MC_AOT_RAYON_MUTABLE_REFS')
    rechazo = compilar(jar_mutable, c_mutable / 'rechazado', sin_optin)
    if rechazo.returncode == 0 or 'captura de referencia debe ser final' not in rechazo.stderr \
            or (c_mutable / 'rechazado').exists():
        raise AssertionError(('sin-optin', rechazo.returncode, rechazo.stderr))

    # El control con campo final compila tambien sin el opt-in: el opt-in no cambia ese camino.
    c_final, jar_final = build(d, source_final, 'final-sin-optin')
    ok(compilar(jar_final, c_final / 'native', sin_optin))
    java_final = ok(run([str(jdk / 'java'), '-cp', str(c_final), 'Driver', *map(str, valores)], capture_output=True))
    nativo_final = ok(run([str(c_final / 'native'), *map(str, valores)], capture_output=True, env=nativo_env))
    if java_final.stdout != nativo_final.stdout:
        raise AssertionError(('final-sin-optin', java_final.stdout[:200], nativo_final.stdout[:200]))
    total += len(valores)

    # Sin el opt-in de referencias de proyecto tampoco se traduce una clase del proyecto.
    sin_proyecto = env.copy()
    sin_proyecto.pop('MC_AOT_RAYON_PROJECT_REFERENCES')
    otro = compilar(jar_final, d / 'sin-proyecto', sin_proyecto)
    if otro.returncode == 0 or (d / 'sin-proyecto').exists():
        raise AssertionError(('sin-referencias-proyecto', otro.returncode, otro.stderr))

    print(f'OK: {total} resultados Java 25/Rayon con campo de referencia no final escrito fuera del constructor '
          f'bajo `MC_AOT_RAYON_MUTABLE_REFS=1`, mas el control con campo final y dos guardas (sin opt-in de '
          f'referencias mutables se rechaza con "captura de referencia debe ser final"; sin referencias de proyecto '
          f'no hay traduccion); sin reclamo de modelo de memoria, solo valores e invariantes')
