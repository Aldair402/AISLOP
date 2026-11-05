#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JAR="${SERVER_JAR:-$ROOT/downloads/server-26.3.jar}"
: "${GRAALVM_HOME:?Define GRAALVM_HOME apuntando a un GraalVM JDK 25 con native-image}"
NATIVE_IMAGE="$GRAALVM_HOME/bin/native-image"
[[ -x "$NATIVE_IMAGE" ]] || { echo "No existe $NATIVE_IMAGE" >&2; exit 1; }
command -v python3 >/dev/null
command -v gcc >/dev/null
# La carpeta temporal queda fuera del proyecto; no se modifica el JAR original.
WORK="$(mktemp -d "${TMPDIR:-/tmp}/mc-graal.XXXXXXXX")"
trap 'rm -rf "$WORK"' EXIT
export JAR WORK
python3 - <<'PY'
import hashlib, os, pathlib, zipfile
jar = os.environ['JAR']
work = pathlib.Path(os.environ['WORK'])
with zipfile.ZipFile(jar) as z:
    main = z.read('META-INF/main-class').decode().strip()
    entries=[]
    for kind in ('libraries', 'versions'):
        for line in z.read(f'META-INF/{kind}.list').decode().splitlines():
            checksum, _, rel = line.split('\t')
            path = pathlib.PurePosixPath(rel)
            if path.is_absolute() or '..' in path.parts:
                raise SystemExit('Ruta insegura en el JAR')
            member = f'META-INF/{kind}/{rel}'
            data = z.read(member)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise SystemExit(f'Checksum incorrecto: {member}')
            dest = work / kind / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            entries.append(str(dest))
    (work/'classpath').write_text(os.pathsep.join(entries))
    (work/'main-class').write_text(main)
print(f'Verificados y extraídos {len(entries)} JARs de Minecraft y sus dependencias.')
PY
CLASSPATH=$(cat "$WORK/classpath")
MAIN=$(cat "$WORK/main-class")
mkdir -p "$ROOT/graal-test/output"
echo "Intentando compilar $MAIN; no se acepta EULA ni se inicia el servidor."
# Experimento inicial: sin metadatos específicos de alcance de Minecraft 26.3.
"$NATIVE_IMAGE" --no-fallback -O0 -J-Xmx"${BUILD_HEAP:-1100m}" \
  --parallelism="${BUILD_THREADS:-2}" --enable-url-protocols=https \
  --initialize-at-run-time=io.netty \
  -cp "$CLASSPATH" "$MAIN" "$ROOT/graal-test/output/minecraft-26.3-native"
