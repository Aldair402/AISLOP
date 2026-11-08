#!/usr/bin/env python3
"""A-02 experimental: validar layouts de grafo para el harness; NO conecta Main.

Se apoya en `mc-aot inspect`, no es un verificador JVM. El consumidor debe
compilar el mismo JAR identificado por hash y registrar/publicar manualmente.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import struct
import subprocess
import sys
import zipfile

NAME = re.compile(r'net/minecraft/(?:[A-Za-z0-9_$]+/)*[A-Za-z0-9_$]+\Z')
# Descriptor -> variante de NumericGraphSlot. boolean/byte/char/short se guardan
# en la misma ranura física que int (V::I), pero el layout conserva el tipo
# declarado: el traductor necesita saber qué anchura recortar al escribir.
PRIMITIVE_SLOTS = {'Z': 'bool', 'B': 'byte', 'C': 'char', 'S': 'short',
                   'I': 'int', 'J': 'long', 'F': 'float', 'D': 'double'}
MEMBER = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


# Bases fuera del JAR que no aportan estado de instancia. Se listan una a una y
# con prueba (`check-vanilla-layout-profile.py` comprueba por reflexión que
# `java.lang.Record` no declara campos de instancia): no se adivina.
EXTERNAL_EMPTY_BASES = {'java/lang/Record'}

_CLASSFILE = None


def classfile_parser():
    """El parser puro-Python del suite, cargado sin depender del nombre del fichero."""
    global _CLASSFILE
    if _CLASSFILE is None:
        path = pathlib.Path(__file__).with_name('classfile-surface.py')
        spec = importlib.util.spec_from_file_location('classfile_surface', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CLASSFILE = module
    return _CLASSFILE


_EXTENDED = {}
_JAR_BYTES = {}


def read_jar(jar):
    """Bytes y digest del JAR, cacheados por identidad del fichero.

    Sin caché, verificar 165 clases de un JAR de 80 MB lee y hashea 13 GB. La
    clave incluye tamaño y `mtime_ns`, así que un JAR modificado se relee y el
    chequeo «el JAR no cambió durante la inspección» sigue significando algo.
    """
    stat = jar.stat()
    key = (str(jar), stat.st_size, stat.st_mtime_ns, stat.st_ino)
    if key not in _JAR_BYTES:
        blob = jar.read_bytes()
        _JAR_BYTES.clear()
        _JAR_BYTES[key] = (blob, sha(blob))
    return _JAR_BYTES[key]


_INTERFACES = {}


def interface_classes(jar, blob):
    """Clases del JAR marcadas ACC_INTERFACE: no tienen instancias ni layout."""
    key = (str(jar), sha(blob))
    if key in _INTERFACES:
        return _INTERFACES[key]
    parser = classfile_parser()
    found = set()
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for entry in z.namelist():
            if not entry.endswith('.class'):
                continue
            try:
                surface = parser.parse_class(z.read(entry))
            except (ValueError, IndexError, struct.error):
                continue
            if surface['flag_bits'] & 0x0200:
                found.add(surface['this_class'])
    _INTERFACES[key] = found
    return found


def extended_classes(jar, blob):
    """Clases que alguna otra clase del JAR extiende.

    Es la comprobación de tipo cerrado que no exige `final`: en un mundo AOT
    cerrado, una clase sin subclases en el JAR no puede recibir instancias de un
    subtipo, así que su layout es igual de exacto que el de una clase `final`.
    Se lee el `super_class` real del classfile, no el texto de una constante.
    """
    key = (str(jar), sha(blob))
    if key in _EXTENDED:
        return _EXTENDED[key]
    parser = classfile_parser()
    extended = set()
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for entry in z.namelist():
            if not entry.endswith('.class'):
                continue
            try:
                surface = parser.parse_class(z.read(entry))
            except (ValueError, IndexError, struct.error):
                # Un classfile roto no aporta jerarquía; el resto de comprobaciones
                # (duplicados, raíz ausente, inspección del root) lo denuncian aparte.
                continue
            if surface['super_class']:
                extended.add(surface['super_class'])
    _EXTENDED[key] = extended
    return extended


def header(text, name):
    matches = re.findall(r'^' + re.escape(name) + r': (.*)$', text, re.M)
    if len(matches) != 1:
        raise ValueError('inspect: cabecera ausente/duplicada: ' + name)
    return matches[0]


def inspect_class(compiler, jar, klass, expected_jar_sha256):
    """Superficie declarada de una clase según `mc-aot inspect`, ya validada."""
    p = subprocess.run([str(compiler), 'inspect', str(jar), klass],
                       capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise ValueError('inspect rechazó classfile: ' + p.stderr[-1000:])
    if read_jar(jar)[1] != expected_jar_sha256:
        raise ValueError('JAR cambió durante inspección')
    text = p.stdout
    if header(text, 'Clase') != klass:
        raise ValueError('clase o superclase incompatible: ' + klass)
    flags_text = header(text, 'Flags')
    if not re.fullmatch(r'0x[0-9a-fA-F]{4}', flags_text):
        raise ValueError('flags inválidos')
    fm = re.search(r'^Campos \((\d+)\):\n(.*?)^Métodos \((\d+)\):\n(.*)\Z', text, re.M | re.S)
    if not fm:
        raise ValueError('inspect: secciones incompletas')
    field_count, field_block, method_count, method_block = fm.groups()
    field_lines = field_block.splitlines()
    if not field_lines or field_lines.pop() != '':
        raise ValueError('inspect: separador de campos inválido')
    method_lines = method_block.splitlines() if method_block else []
    if len(field_lines) != int(field_count) or len(method_lines) != int(method_count):
        raise ValueError('inspect: conteo de miembros inconsistente')
    if len(field_lines) > 256:
        raise ValueError('demasiados campos')
    if any(not re.match(r'^  0x[0-9a-fA-F]{4} \S+\([^ ]*\)\S+ \| code=', line) for line in method_lines):
        raise ValueError('inspect: método inválido')
    return {'super': header(text, 'Superclase'),
            'flags': int(flags_text, 16),
            'interfaces': header(text, 'Interfaces').strip(),
            'field_lines': field_lines,
            'has_clinit': any(re.match(r'^  0x[0-9a-fA-F]{4} <clinit>\(', line) for line in method_lines)}


def instance_fields(info, klass, allow_mutable_refs, class_names):
    """Campos de instancia del classfile y lo que bloquea *ejecutar* la clase.

    Un campo estático no ocupa el objeto y un `<clinit>` no cambia el layout de
    una instancia: se anotan como bloqueos de ejecución, no como rechazo del
    layout. Las interfaces tampoco describen campos: afectan al despacho.
    Lo que sí expulsa a la clase es un descriptor que el puente no sabe
    representar en una ranura (J/F/D/Z/B/C/S), un campo `volatile` o `int final`.
    """
    fields, seen, blockers, names = [], set(), [], []
    for line in info['field_lines']:
        m = re.fullmatch(r'  0x([0-9a-fA-F]{4}) (\S+) (\S+)', line)
        if not m:
            raise ValueError('inspect: campo inválido')
        flag, field, desc = m.groups()
        flag = int(flag, 16)
        if not MEMBER.fullmatch(field) or (field, desc) in seen:
            raise ValueError('nombre inválido o campo duplicado')
        seen.add((field, desc))
        if flag & 0x08:
            if 'campos estáticos' not in blockers:
                blockers.append('campos estáticos')
            continue
        if flag & 0x40:
            raise ValueError('campos volatile no soportados: ' + klass)
        if desc in PRIMITIVE_SLOTS:
            # `final` en un campo es una restricción de escritura, no otra ranura:
            # el layout es el mismo y se anota para que el traductor pueda negar
            # la escritura en vez de olvidarla.
            fields.append({'name': field, 'descriptor': desc,
                           'kind': PRIMITIVE_SLOTS[desc],
                           'final': bool(flag & 0x10), 'declared_in': klass})
        elif desc.startswith('L') and desc.endswith(';'):
            target = desc[1:-1]
            if not flag & 0x10 and not allow_mutable_refs:
                raise ValueError('referencia no final: ' + klass)
            # Se admiten referencias a clases con bytes en el JAR (de cualquier
            # paquete) y a interfaces: el layout de una ranura es una referencia,
            # no una promesa sobre el destino. Lo que no se admite es un tipo del
            # que no tenemos bytes: ahí la ranura prometería algo que no se puede
            # describir ni ejecutar.
            if target not in class_names:
                raise ValueError('referencia fuera del JAR (sin bytes que describir): ' + klass)
            fields.append({'name': field, 'descriptor': desc,
                           'kind': 'ref' if flag & 0x10 else 'mutref',
                           'target': target, 'target_kind': 'pending',
                           'declared_in': klass})
            names.append(target)
        else:
            raise ValueError('descriptor de campo no soportado: ' + desc)
    if info['has_clinit']:
        blockers.append('clinit')
    if info['interfaces']:
        blockers.append('interfaces: ' + info['interfaces'].replace(',', ' '))
    return fields, blockers, names


def verify(jar, root, compiler, expected_jar_sha256, allow_mutable_refs=False):
    jar = pathlib.Path(jar)
    compiler = pathlib.Path(compiler)
    if not NAME.fullmatch(root):
        raise ValueError('clase raíz fuera del perfil')
    if not DIGEST.fullmatch(expected_jar_sha256):
        raise ValueError('SHA-256 esperado inválido')
    blob, digest = read_jar(jar)
    if digest != expected_jar_sha256:
        raise ValueError('hash del JAR no coincide')
    # Solo JAR directo, sin multi-release; no confiar en la selección de otra
    # versión ni aceptar nombres duplicados. El parser Rust recibe el mismo JAR.
    extended = extended_classes(jar, blob)
    target_interfaces = interface_classes(jar, blob)
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        all_names = [entry.filename for entry in z.infolist()]
        if len(all_names) != len(set(all_names)):
            raise ValueError('entradas JAR duplicadas')
        if any(n.startswith('META-INF/versions/') and n.endswith('.class') for n in all_names):
            raise ValueError('JAR multi-release fuera del perfil')
        names = set(all_names)
        class_names = {entry[:-6] for entry in names if entry.endswith('.class')}
        cache = {}

        def load(klass):
            """Clase inspeccionada y validada; cacheada para no repetir trabajo."""
            if klass in cache:
                return cache[klass]
            if len(cache) >= 64:
                raise ValueError('límite de 64 clases en grafo')
            if klass + '.class' not in names:
                raise ValueError('clase de referencia ausente: ' + klass)
            info = inspect_class(compiler, jar, klass, expected_jar_sha256)
            info['sha256'] = sha(z.read(klass + '.class'))
            info['fields'], info['execution_blockers'], info['refs'] = instance_fields(
                info, klass, allow_mutable_refs, class_names)
            cache[klass] = info
            return info

        def hierarchy(klass, top=False):
            """Cadena desde `java/lang/Object` hasta `klass`, sin ciclos."""
            links, seen, current = [], set(), klass
            while current and current != 'java/lang/Object' and current not in EXTERNAL_EMPTY_BASES:
                if current in seen:
                    raise ValueError('ciclo de superclases: ' + klass)
                seen.add(current)
                info = load(current)
                # Una interfaz, anotación o enum no describe un objeto ordinario.
                # Una clase abstracta sí: su layout es el prefijo de sus hijas y
                # este verificador describe campos, no instanciación.
                if info['flags'] & (0x0200 | 0x2000 | 0x4000):
                    raise ValueError('interfaz/annotation/enum fuera del perfil: ' + current)
                if not top and info['flags'] & 0x0200:
                    raise ValueError('interfaz en la cadena de superclases: ' + current)
                links.append(current)
                current = info['super']
            if current is None:
                raise ValueError('superclase ausente: ' + klass)
            return list(reversed(links))

        layouts = {}

        def layout_of(klass):
            """Layout completo: campos de los ancestros primero, luego los propios.

            El prefijo heredado es lo que hace que un campo declarado en el padre
            tenga el mismo índice en el layout de cualquier descendiente; el
            objecto se ata con el layout de **su** clase (`attach` exige que el
            nombre coincida), así que las dos reglas juntas son la garantía.
            """
            if klass in layouts:
                return layouts[klass]
            ordered = hierarchy(klass)
            fields, blockers, own = [], [], 0
            for link in ordered:
                info = cache[link]
                fields.extend(info['fields'])
                blockers.extend(info['execution_blockers'])
                own = len(info['fields'])
            base = cache[klass]
            if base['flags'] & 0x10:
                closed_by = 'final'
            elif klass in extended:
                closed_by = 'has-subclasses'
            else:
                closed_by = 'no-subclasses'
            entry = {'class': klass, 'sha256': base['sha256'], 'super': base['super'],
                     'closed_by': closed_by, 'own_field_count': own,
                     'execution_blockers': blockers, 'fields': fields}
            # Un objeto de una interfaz no existe: la ranura es una referencia,
            # no una promesa de layout del destino.
            for link in ordered:
                for field in cache[link]['fields']:
                    if field['kind'] not in ('ref', 'mutref'):
                        continue
                    target = field['target']
                    if target in target_interfaces:
                        field['target_kind'] = 'interface'
            layouts[klass] = entry
            # Un layout no termina en su clase, pero tampoco puede exigir el
            # layout de todo lo que referencia: si el destino no se puede
            # describir, se anota como bloqueo y se sigue. Leer por esa ranura
            # fallará cerrado en vez de inventar un layout.
            for link in ordered:
                for target in cache[link]['refs']:
                    if target in layouts:
                        continue
                    try:
                        layout_of(target)
                    except ValueError as error:
                        for field in cache[link]['fields']:
                            if field.get('target') == target and field['kind'] in ('ref', 'mutref'):
                                field['target_kind'] = 'sin-layout'
                        if not any(b.startswith('destino sin layout: ' + target)
                                   for b in entry['execution_blockers']):
                            entry['execution_blockers'].append('destino sin layout: ' + target
                                                               + ' (' + str(error) + ')')
                    else:
                        for field in cache[link]['fields']:
                            if field.get('target') == target and field['kind'] in ('ref', 'mutref'):
                                field['target_kind'] = 'class'
            return entry

        root_layout = layout_of(root)

    if read_jar(jar)[1] != expected_jar_sha256:
        raise ValueError('JAR cambió durante inspección')
    ordered_classes = [layouts[root]] + [item for klass, item in layouts.items() if klass != root]
    return {'schema': 'numeric-graph-layout-v2', 'jar_sha256': expected_jar_sha256,
            'root': root, 'classes': ordered_classes,
            'limitations': ('Solo layouts; sin verifier JVM, registro/publicación automática, ni Main. '
                            'Ranuras: int, bool, byte, char, short, long, float, double y referencias. '
                            'Campos heredados primero; el objeto se ata con el layout de su clase exacta, '
                            'así que una subclase no traducida falla en `attach` en vez de corromper. '
                            'Estáticos, <clinit> e interfaces se declaran en execution_blockers: bloquean '
                            'ejecutar la clase, no describir su layout.')}


RUST_SLOT = {'int': 'Int', 'bool': 'Bool', 'byte': 'Byte', 'char': 'Char',
             'short': 'Short', 'long': 'Long', 'float': 'Float', 'double': 'Double'}


def rust_layouts(result):
    lines = []
    for i, item in enumerate(result['classes']):
        slots = []
        for field in item['fields']:
            if field['kind'] in RUST_SLOT:
                slots.append('NumericGraphSlot::' + RUST_SLOT[field['kind']])
            elif field['kind'] == 'ref':
                slots.append('NumericGraphSlot::Ref(' + json.dumps(field['target'], ensure_ascii=True) + ')')
            else:
                slots.append('NumericGraphSlot::MutRef(' + json.dumps(field['target'], ensure_ascii=True) + ')')
        lines.append('static LAYOUT_' + str(i) + ':NumericGraphLayout=NumericGraphLayout{class:'
                     + json.dumps(item['class'], ensure_ascii=True) + ',fields:&[' + ','.join(slots) + ']};')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=pathlib.Path)
    parser.add_argument('root')
    parser.add_argument('--compiler', required=True, type=pathlib.Path)
    parser.add_argument('--jar-sha256', required=True)
    parser.add_argument('--format', choices=['json', 'rust'], default='json')
    # Opt-in: un campo de referencia no final es escribible y debe probarse aparte.
    parser.add_argument('--allow-mutable-refs', action='store_true')
    args = parser.parse_args()
    result = verify(args.jar, args.root, args.compiler, args.jar_sha256, args.allow_mutable_refs)
    print(rust_layouts(result) if args.format == 'rust' else json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(2)
