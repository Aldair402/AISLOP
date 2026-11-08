#!/usr/bin/env python3
"""Censo exploratorio de generación de Rust para clases completas.

El censo de layouts (`layout-profile-census.py`) dice qué clases se pueden *describir*;
este dice qué clases se pueden *traducir enteras* con el traductor actual, que es la
condición necesaria para ejecutar una clase completa (no un método suelto).

Se apoya en `mc-aot class-demo-rs`: genera Rust con las mismas guardas que
`class-demo`, pero no invoca rustc. Un resultado favorable NO demuestra que Rust
compile, que la clase se ejecute ni su equivalencia con Java; requiere pruebas
independientes. Los bloqueos son el primer error observado, no todos los posibles.
"""
import argparse
import concurrent.futures
import importlib.util
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
project = root.parent
CENSUS = root / 'tools' / 'layout-profile-census.py'
COMPILER = root / 'target/debug/mc-aot'
DEFAULT_JAR = project / 'downloads/server-26.3-inner.jar'

# Un nombre de clase o descriptor concreto no es un motivo: dos clases que fallan por
# "referencia ausente: X" fallan por lo mismo. Se normaliza antes de contar.
NAMED = re.compile(r'(?:net|java|javax|jdk|com|org|io|it|sun)/[A-Za-z0-9_$/]+')
OBJECT = re.compile(r'\[*(?:L[A-Za-z0-9_$/]+;)')
ARRAY = re.compile(r'\[+[ZBCSIJFD]')
OPTION = re.compile(r'Some\("?([^")]*)"?\)')
HEX = re.compile(r'0x[0-9a-f]+')
# Lo que queda tras los dos puntos es un nombre de la propia clase: un campo, un
# método o la clase base. Se sustituye por su forma (mayúscula = clase, si no = miembro)
# para que el motivo sea comparable entre clases distintas.
TAIL = re.compile(r'(?<=: )([A-Za-z_$][A-Za-z0-9_$]*)(?![A-Za-z0-9_$<])')


def layout_census():
    spec = importlib.util.spec_from_file_location('layout_profile_census', CENSUS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(message):
    text = message.strip().splitlines()[-1] if message.strip() else 'sin mensaje'
    text = re.sub(r'^Error:\s*', '', text)
    text = OPTION.sub('<clase>', text)
    text = OBJECT.sub('<clase>', text)
    text = ARRAY.sub('<array>', text)
    text = NAMED.sub('<clase>', text)
    text = HEX.sub('<hex>', text)
    head = text.split(': ', 1)[0]
    label = '<campo>' if head.startswith('campo') else ('<clase>' if head.startswith(('base', 'interfaz', 'clases')) else '<miembro>')
    text = TAIL.sub(lambda m: label if (label == '<campo>' or m.group(1)[:1].isupper()) else '<miembro>', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def translate(compiler, jar, name, scratch):
    """(clase, None) si la traducción completa pasa; (clase, motivo) si no."""
    # Cada invocación tiene su propio archivo: no compartir escrituras entre hilos.
    with tempfile.TemporaryDirectory(dir=scratch) as td:
        out = pathlib.Path(td) / 'out.rs'
        try:
            done = subprocess.run([str(compiler), 'class-demo-rs', str(jar), name, str(out)],
                                  capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return name, 'tiempo agotado (120 s)'
        if done.returncode == 0 and not out.is_file():
            raise RuntimeError(f'{name}: el compilador no creó el archivo prometido')
    if done.returncode == 0:
        return name, None
    return name, normalize(done.stderr or done.stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jar', type=pathlib.Path, default=DEFAULT_JAR)
    ap.add_argument('--compiler', type=pathlib.Path, default=COMPILER)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--limit', type=int, help='solo las N primeras clases (para probar)')
    ap.add_argument('--only-admitted', action='store_true',
                    help='solo las clases sin bloqueo de layout (el universo describible)')
    ap.add_argument('--out', type=pathlib.Path, help='escribe el resultado en JSON')
    args = ap.parse_args()
    if args.jobs < 1 or (args.limit is not None and args.limit < 1):
        ap.error('--jobs y --limit deben ser positivos')
    if not args.jar.is_file():
        ap.error(f'no existe el JAR: {args.jar}')
    if not args.compiler.exists():
        sys.exit(f'falta el compilador {args.compiler}: cargo build --manifest-path mc-aot/Cargo.toml')

    module = layout_census()
    rows = module.census(args.jar)
    universe = [r['class'] for r in rows if not (args.only_admitted and r['layout_blockers'])]
    if args.limit:
        universe = universe[:args.limit]
    fail = {}

    with tempfile.TemporaryDirectory(prefix='mc-exec-census-') as td:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(translate, args.compiler, args.jar, name,
                                   pathlib.Path(td)) for name in universe]
            for done in concurrent.futures.as_completed(futures):
                name, reason = done.result()
                if reason is not None:
                    fail[name] = reason

    fail = dict(sorted(fail.items()))
    ok = [n for n in universe if n not in fail]
    reasons = {}
    for reason in fail.values():
        reasons[reason] = reasons.get(reason, 0) + 1
    ranked = sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))

    admitted = {r['class'] for r in rows if not r['layout_blockers']}
    admitted_ok = [n for n in ok if n in admitted]
    summary = {
        'jar': str(args.jar),
        'jar_sha256': hashlib.sha256(args.jar.read_bytes()).hexdigest(),
        'compiler_sha256': hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
        'universe': 'describibles (sin bloqueo de layout)' if args.only_admitted else 'todo el JAR',
        'total': len(universe),
        'traducen_enteras': len(ok),
        'bloqueadas': len(fail),
        'admitted_total': len(admitted),
        'admitted_ok': len(admitted_ok),
        'reasons': [{'motivo': m, 'clases': c} for m, c in ranked],
        'ok': ok,
        'fail': fail,
    }
    print(f"universo: {len(universe)} clases ({summary['universe']})")
    print(f"generan Rust (sin rustc ni ejecución): {len(ok)}  ({100.0 * len(ok) / max(1, len(universe)):.1f} %)"
          f"  · bloqueadas: {len(fail)}")
    print(f"de las describibles: {len(admitted_ok)} de {len(admitted)}")
    print('\nprimeros motivos de bloqueo:')
    for motivo, count in ranked[:15]:
        print(f'  {count:5d}  {motivo}')
    if args.out:
        args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
        print(f'\nJSON: {args.out}')


if __name__ == '__main__':
    main()
