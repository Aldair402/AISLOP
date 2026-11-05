#!/bin/sh
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v java >/dev/null 2>&1 || { echo 'Java no está instalado o no está en PATH.' >&2; exit 1; }
mkdir -p "$ROOT/analysis/decompiled-cfr"
exec java -jar "$ROOT/tools/cfr-0.152.jar" "$ROOT/downloads/server-26.3-inner.jar" --outputdir "$ROOT/analysis/decompiled-cfr"
