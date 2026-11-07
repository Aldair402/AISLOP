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
MEMBER = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


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
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        all_names = [entry.filename for entry in z.infolist()]
        if len(all_names) != len(set(all_names)):
            raise ValueError('entradas JAR duplicadas')
        if any(n.startswith('META-INF/versions/') and n.endswith('.class') for n in all_names):
            raise ValueError('JAR multi-release fuera del perfil')
        names = set(all_names)
        classes = {}
        pending = [root]
        while pending:
            klass = pending.pop(0)
            if klass in classes:
                continue
            if len(classes) >= 64:
                raise ValueError('límite de 64 clases en grafo')
            name = klass + '.class'
            if name not in names:
                raise ValueError('clase de referencia ausente: ' + klass)
            class_hash = sha(z.read(name))
            p = subprocess.run([str(compiler), 'inspect', str(jar), klass],
                               capture_output=True, text=True, timeout=60)
            if p.returncode:
                raise ValueError('inspect rechazó classfile: ' + p.stderr[-1000:])
            if read_jar(jar)[1] != expected_jar_sha256:
                raise ValueError('JAR cambió durante inspección')
            text = p.stdout
            if header(text, 'Clase') != klass or header(text, 'Superclase') != 'java/lang/Object':
                raise ValueError('clase o superclase incompatible: ' + klass)
            flags_text = header(text, 'Flags')
            if not re.fullmatch(r'0x[0-9a-fA-F]{4}', flags_text):
                raise ValueError('flags inválidos')
            flags = int(flags_text, 16)
            if flags & (0x0200 | 0x0400 | 0x2000 | 0x4000):
                raise ValueError('clase no puede ser abstracta/interfaz/enum: ' + klass)
            # Tipo cerrado: `final` o, en mundo cerrado, sin subclases en el JAR.
            if not flags & 0x10 and klass in extended:
                raise ValueError('clase debe ser final o estar cerrada (tiene subclases en el JAR): ' + klass)
            closed_by = 'final' if flags & 0x10 else 'no-subclasses'
            if header(text, 'Interfaces').strip():
                raise ValueError('interfaces no soportadas: ' + klass)
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
            if any(re.match(r'^  0x[0-9a-fA-F]{4} <clinit>\(', line) for line in method_lines):
                raise ValueError('inicializador de clase no soportado: ' + klass)
            if any(not re.match(r'^  0x[0-9a-fA-F]{4} \S+\([^ ]*\)\S+ \| code=', line) for line in method_lines):
                raise ValueError('inspect: método inválido')
            fields = []
            seen = set()
            for line in field_lines:
                m = re.fullmatch(r'  0x([0-9a-fA-F]{4}) (\S+) (\S+)', line)
                if not m:
                    raise ValueError('inspect: campo inválido')
                flag, field, desc = m.groups()
                flag = int(flag, 16)
                if not MEMBER.fullmatch(field) or (field, desc) in seen:
                    raise ValueError('nombre inválido o campo duplicado')
                seen.add((field, desc))
                if flag & 0x08:
                    raise ValueError('campos estáticos no soportados: ' + klass)
                if flag & 0x40:
                    raise ValueError('campos volatile no soportados: ' + klass)
                if desc == 'I':
                    if flag & 0x10:
                        raise ValueError('int final no soportado: ' + klass)
                    fields.append({'name': field, 'descriptor': desc, 'kind': 'int'})
                elif desc.startswith('L') and desc.endswith(';'):
                    target = desc[1:-1]
                    if not flag & 0x10 and not allow_mutable_refs:
                        raise ValueError('referencia no final: ' + klass)
                    if not NAME.fullmatch(target):
                        raise ValueError('referencia fuera del perfil: ' + klass)
                    fields.append({'name': field, 'descriptor': desc, 'kind': 'ref' if flag & 0x10 else 'mutref', 'target': target})
                    if target not in classes and target not in pending:
                        pending.append(target)
                else:
                    raise ValueError('descriptor de campo no soportado: ' + desc)
            classes[klass] = {'class': klass, 'sha256': class_hash,
                              'closed_by': closed_by, 'fields': fields}
    if read_jar(jar)[1] != expected_jar_sha256:
        raise ValueError('JAR cambió durante inspección')
    return {'schema': 'numeric-graph-layout-v1', 'jar_sha256': expected_jar_sha256,
            'root': root, 'classes': list(classes.values()),
            'limitations': ('Solo layouts; sin verifier JVM, registro/publicación automática, ni Main. '
                            'Tipo cerrado = final o sin subclases en este JAR (mundo cerrado): '
                            'si aparece una subclase nueva, el layout deja de valer.')}


def rust_layouts(result):
    lines = []
    for i, item in enumerate(result['classes']):
        slots = []
        for field in item['fields']:
            if field['kind'] == 'int':
                slots.append('NumericGraphSlot::Int')
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
