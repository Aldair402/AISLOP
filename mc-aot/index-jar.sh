#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
JAR="${1:-$ROOT/../downloads/server-26.3-inner.jar}"
OUTPUT="${2:-$ROOT/../analysis/class-index.tsv}"
GRAPH="${3:-$ROOT/../analysis/class-dependencies.tsv.gz}"
[[ -f "$JAR" ]] || { echo "No existe el JAR interno: $JAR" >&2; exit 1; }
[[ "$OUTPUT" != "$GRAPH" ]] || { echo 'El índice y el grafo deben tener rutas distintas' >&2; exit 1; }
command -v unzip >/dev/null || { echo 'Falta unzip' >&2; exit 1; }
command -v gzip >/dev/null || { echo 'Falta gzip' >&2; exit 1; }
command -v cargo >/dev/null || { echo 'Falta cargo' >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT")" "$(dirname "$GRAPH")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/mc-index.XXXXXXXX")"
trap 'rm -rf "$WORK"' EXIT
# Solo JARs de confianza; descomprime archivos .class para análisis estructural.
unzip -q "$JAR" '*.class' -d "$WORK"
# Se escriben temporales primero: un fallo no reemplaza resultados previos.
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- index-dir "$WORK" > "$WORK/index.tmp"
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -- graph-dir "$WORK" | gzip -c > "$WORK/graph.tmp"
mv "$WORK/index.tmp" "$OUTPUT"
mv "$WORK/graph.tmp" "$GRAPH"
echo "Índice: $OUTPUT" >&2
echo "Dependencias estáticas: $GRAPH" >&2
