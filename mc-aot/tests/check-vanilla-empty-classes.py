#!/usr/bin/env python3
"""Constructores de seis clases vanilla sin métodos/campos declarados.

Son casos triviales: no miden cobertura de lógica de Minecraft ni arranque.
El driver usa reflexión para el constructor privado; no afirma comprobación de
acceso Java en el CLI de class-demo.
"""
import os
import pathlib
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
jar = root.parent / 'downloads/server-26.3-inner.jar'
compiler = root / 'target/debug/mc-aot'
jdk = pathlib.Path(os.environ['JAVA_HOME']) / 'bin'
classes = [
    'net/minecraft/server/packs/resources/PreparableReloadListener$StateKey',
    'net/minecraft/world/item/equipment/EquipmentAsset',
    'net/minecraft/world/level/levelgen/GenerationStep',
    'net/minecraft/world/level/levelgen/structure/structures/BuriedTreasurePieces',
    'net/minecraft/world/level/levelgen/structure/structures/OceanMonumentPieces',
    'net/minecraft/world/waypoints/WaypointStyleAsset',
]

DRIVER = '''
import java.lang.reflect.*;
public class EmptyOracle {
  public static void main(String[] names) throws Exception {
    for (String name : names) {
      Class<?> c = Class.forName(name.replace('/', '.'));
      if (c.getDeclaredFields().length != 0 || c.getDeclaredMethods().length != 0 ||
          c.getDeclaredConstructors().length != 1 ||
          c.getDeclaredConstructors()[0].getParameterCount() != 0)
        throw new AssertionError("la superficie cambió: " + name);
      Constructor<?> k = c.getDeclaredConstructor();
      k.setAccessible(true);
      if (k.newInstance() == null) throw new AssertionError(name);
      System.out.println("OK");
    }
  }
}
'''

def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=180, **kwargs)

with tempfile.TemporaryDirectory(prefix='mc-empty-classes-') as td:
    d = pathlib.Path(td)
    (d / 'EmptyOracle.java').write_text(DRIVER)
    compile_java = run([jdk / 'javac', '-d', d, d / 'EmptyOracle.java'])
    assert compile_java.returncode == 0, compile_java.stderr
    java = run([jdk / 'java', '-cp', f'{d}{os.pathsep}{jar}', 'EmptyOracle', *classes])
    assert java.returncode == 0, java.stderr
    lines = java.stdout.splitlines()
    assert len(lines) == len(classes), lines
    for i, name in enumerate(classes):
        binary = d / f'empty-{i}'
        compiled = run([compiler, 'class-demo', jar, name, binary])
        assert compiled.returncode == 0, (name, compiled.stderr)
        native = run([binary, 'new'], env=dict(os.environ, PATH='/nonexistent'))
        assert native.returncode == 0 and native.stdout.splitlines() == [lines[i]], (name, native.stderr, native.stdout)
    print(f'OK: {len(classes)} clases sin miembros declarados: constructor completo cotejado con Java 25, binarios sin Java; un constructor privado por reflexión')
