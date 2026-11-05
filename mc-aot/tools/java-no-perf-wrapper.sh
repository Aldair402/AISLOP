#!/usr/bin/env bash
# Crear JAVA_HOME temporal para los tests: mismo JDK, sin ficheros hsperfdata.
# Uso: java-no-perf-wrapper.sh /ruta/al/jdk /ruta/nueva/de/salida
set -euo pipefail
if [[ $# != 2 || ! -x "$1/bin/java" || -e "$2" ]]; then
  echo 'uso: java-no-perf-wrapper.sh <jdk-existente> <directorio-nuevo>' >&2
  exit 2
fi
jdk=$(cd "$1" && pwd -P)
mkdir -p "$2/bin"
out=$(cd "$2" && pwd -P)
for file in "$jdk"/*; do
  [[ ${file##*/} == bin ]] || ln -s "$file" "$out/${file##*/}"
done
for file in "$jdk"/bin/*; do
  [[ ${file##*/} == java ]] || ln -s "$file" "$out/bin/${file##*/}"
done
# %q protege espacios y caracteres especiales. El ejecutable real es el del JDK.
printf '#!/usr/bin/env bash\nexec %q -XX:-UsePerfData "$@"\n' "$jdk/bin/java" > "$out/bin/java"
chmod +x "$out/bin/java"
printf '%s\n' "$out"
