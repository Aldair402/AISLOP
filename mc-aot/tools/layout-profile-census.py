#!/usr/bin/env python3
"""A-02 fase 2: qué clase del JAR oficial puede describirse y qué le falta para ejecutarse.

Historia de este fichero, porque importa para no repetir el error: primero se
publicó «0 de 687 candidatas» sin decir qué cláusula fallaba en cada una; después
un censo por cláusulas («el muro es `final`») que resultó ser falso en cuanto se
comprobó el tipo cerrado leyendo el `super_class`. Esta versión aplica **las
mismas reglas que `numeric_bridge_layout.verify`** y separa dos cosas que antes
iban juntas:

- **Bloqueos de layout** (fatal): la clase no se puede describir. Descriptor que
  el puente no sabe representar (`J/F/D/Z/B/C/S`), campo `volatile`, `int final`,
  referencia mutable sin opt-in, nombre fuera del perfil, cadena de superclases
  fuera del perfil o con una interfaz.
- **Bloqueos de ejecución** (anotados, no fatales): campos estáticos, `<clinit>`,
  interfaces y destinos de referencia sin layout. No cambian el layout de un
  objeto; impiden ejecutar la clase.

Uso:
  python3 mc-aot/tools/layout-profile-census.py            # resumen
  python3 mc-aot/tools/layout-profile-census.py --plan     # qué compra cada ranura
  python3 mc-aot/tools/layout-profile-census.py --class net.minecraft.server.players.SleepStatus
  python3 mc-aot/tools/layout-profile-census.py --json /var/tmp/census.json

Exit codes: 0 censo producido; 2 sin JAR.
"""
import argparse
import collections
import importlib.util
import json
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
JAR = ROOT / "downloads" / "server-26.3-inner.jar"
SURFACE = pathlib.Path(__file__).with_name("classfile-surface.py")

NAME = re.compile(r'net/minecraft/(?:[A-Za-z0-9_$]+/)*[A-Za-z0-9_$]+\Z')
FIELD_STATIC, FIELD_FINAL, FIELD_VOLATILE = 0x0008, 0x0010, 0x0040
CLASS_INTERFACE, CLASS_ANNOTATION, CLASS_ENUM = 0x0200, 0x2000, 0x4000

# Bases fuera del JAR sin estado de instancia, verificadas por reflexión en
# `check-vanilla-layout-profile.py`. Deben coincidir con numeric_bridge_layout.
EXTERNAL_EMPTY_BASES = {'java/lang/Record'}

PRIMITIVES = {'Z': 'boolean', 'B': 'byte', 'C': 'char', 'S': 'short',
              'I': 'int', 'J': 'long', 'F': 'float', 'D': 'double'}


def load_parser():
    spec = importlib.util.spec_from_file_location("classfile_surface", SURFACE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def surfaces(jar):
    """Superficie declarada de todas las clases del JAR, indexada por nombre."""
    parser = load_parser()
    out = {}
    with zipfile.ZipFile(jar) as z:
        for entry in sorted(z.namelist()):
            if not entry.endswith('.class') or entry.startswith('META-INF/'):
                continue
            surface = parser.parse_class(z.read(entry))
            out[surface['this_class']] = surface
    return out


def verdict(name, table, allow_mutable_refs=False, slots=frozenset(PRIMITIVES)):
    """(bloqueos de layout, bloqueos de ejecución, campos de instancia)."""
    fatal, execute = [], []
    chain, seen, current = [], set(), name
    while current and current != 'java/lang/Object' and current not in EXTERNAL_EMPTY_BASES:
        if current in seen:
            fatal.append('ciclo de superclases')
            break
        seen.add(current)
        surface = table.get(current)
        if surface is None:
            fatal.append('cadena fuera del JAR: ' + current)
            break
        if not NAME.match(current):
            fatal.append('nombre fuera del perfil')
            break
        if surface['flag_bits'] & (CLASS_INTERFACE | CLASS_ANNOTATION | CLASS_ENUM):
            fatal.append('interfaz/anotación/enum en la cadena: ' + current)
            break
        chain.append(current)
        current = surface['super_class']
    fields = 0
    for klass in reversed(chain):
        surface = table[klass]
        if surface['has_clinit']:
            execute.append('clinit')
        if surface['interfaces']:
            execute.append('interfaces')
        for field in surface['fields']:
            flags, descriptor = field['flag_bits'], field['descriptor']
            if flags & FIELD_STATIC:
                if 'campos estáticos' not in execute:
                    execute.append('campos estáticos')
                continue
            fields += 1
            if flags & FIELD_VOLATILE:
                fatal.append('volatile')
                continue
            if descriptor in PRIMITIVES:
                if descriptor not in slots:
                    fatal.append('sin ranura ' + PRIMITIVES[descriptor])
            elif descriptor.startswith('L') and descriptor.endswith(';'):
                target = descriptor[1:-1]
                if not flags & FIELD_FINAL and not allow_mutable_refs:
                    fatal.append('referencia no final')
                if target not in table:
                    fatal.append('referencia fuera del JAR')
            else:
                fatal.append('descriptor ' + descriptor)
    seen_fatal, seen_exec = [], []
    for item in fatal:
        if item not in seen_fatal:
            seen_fatal.append(item)
    for item in execute:
        if item not in seen_exec:
            seen_exec.append(item)
    return seen_fatal, seen_exec, fields


def census(jar, allow_mutable_refs=False, slots=frozenset(PRIMITIVES)):
    table = surfaces(jar)
    rows = []
    for name, surface in sorted(table.items()):
        fatal, execute, fields = verdict(name, table, allow_mutable_refs, slots)
        rows.append({'class': name,
                     'layout_blockers': fatal,
                     'execution_blockers': execute,
                     'instance_fields': fields,
                     'super': surface['super_class'],
                     'descriptors': sorted({f['descriptor'] for f in surface['fields']
                                            if not f['flag_bits'] & FIELD_STATIC})})
    return rows


def summarize(rows):
    admitted = [r for r in rows if not r['layout_blockers']]
    first = collections.Counter(r['layout_blockers'][0] for r in rows if r['layout_blockers'])
    execute = collections.Counter(b for r in admitted for b in r['execution_blockers'])
    return {'total': len(rows), 'admitted': admitted,
            'with_fields': [r for r in admitted if r['instance_fields']],
            'fields': sum(r['instance_fields'] for r in admitted),
            'first_blocker': first, 'execution': execute}


def plan(rows):
    """Cuántas clases abre añadir ranuras al puente (lo único que falta para describir)."""
    base = sum(1 for r in rows if not r['layout_blockers'])
    base_fields = sum(1 for r in rows if not r['layout_blockers'] and r['instance_fields'])
    steps = [('perfil actual (ocho primitivos y referencias finales)', set(PRIMITIVES))]
    for extra in ('', ):
        pass
    out = []
    for label, slots in steps:
        admitted = [r for r in rows
                    if not [b for b in r['layout_blockers']
                            if not b.startswith('sin ranura') or b.split()[-1] not in
                            [PRIMITIVES[c] for c in slots]]]
        # Recontar con las ranuras concedidas: el bloqueo por ranura desaparece.
        total = 0
        with_fields = 0
        fields = 0
        for row in rows:
            remaining = [b for b in row['layout_blockers']
                         if not (b.startswith('sin ranura')
                                 and b.split()[-1] in [PRIMITIVES[c] for c in slots])]
            if remaining:
                continue
            total += 1
            if row['instance_fields']:
                with_fields += 1
            fields += row['instance_fields']
        out.append({'step': label, 'classes': total,
                    'classes_with_fields': with_fields, 'instance_fields': fields})
    assert out[0]['classes'] == base and out[0]['classes_with_fields'] == base_fields
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jar', type=pathlib.Path, default=JAR)
    ap.add_argument('--json', type=pathlib.Path)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--simulate', action='store_true', help='alias histórico de --plan')
    ap.add_argument('--allow-mutable-refs', action='store_true')
    ap.add_argument('--class', dest='klass')
    ap.add_argument('--limit', type=int, default=15)
    args = ap.parse_args()

    if not args.jar.is_file():
        print(f'ERROR: {args.jar} no existe', file=sys.stderr)
        return 2
    rows = census(args.jar, args.allow_mutable_refs)

    if args.klass:
        wanted = args.klass.replace('.', '/')
        hit = next((r for r in rows if r['class'] == wanted), None)
        if hit is None:
            print(f'ERROR: {wanted} no está en el JAR', file=sys.stderr)
            return 1
        print(json.dumps(hit, indent=2, ensure_ascii=False))
        return 0

    s = summarize(rows)
    print(f"clases en el JAR: {s['total']}")
    print(f"describibles (layout): {len(s['admitted'])}"
          f" — de ellas con campos: {len(s['with_fields'])}"
          f" — campos de instancia: {s['fields']}")
    print('\nprimer bloqueo de layout (fatal):')
    for clause, count in s['first_blocker'].most_common(args.limit):
        print(f'  {count:6d}  {clause}')
    print('\nbloqueos de ejecución entre las describibles (no impiden el layout):')
    for clause, count in s['execution'].most_common(args.limit):
        print(f'  {count:6d}  {clause}')

    if args.plan or args.simulate:
        print('\nplan medido (clases / con campos / campos de instancia):')
        for step in plan(rows):
            print(f"  {step['classes']:5d} / {step['classes_with_fields']:5d} / "
                  f"{step['instance_fields']:6d}  {step['step']}")

    if args.json:
        args.json.write_text(json.dumps(
            {'schema': 'layout-profile-census-v2', 'jar': args.jar.name,
             'allow_mutable_refs': args.allow_mutable_refs,
             'total': s['total'], 'admitted': len(s['admitted']),
             'with_fields': len(s['with_fields']), 'instance_fields': s['fields'],
             'first_blocker': dict(s['first_blocker']),
             'execution': dict(s['execution']), 'classes': rows},
            indent=2, sort_keys=True) + '\n')
        print(f'\nwrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
