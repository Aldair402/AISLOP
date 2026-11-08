#!/usr/bin/env bash
# Fetch the official Mojang server bundle and extract the inner server JAR.
# Both downloads are verified against pinned digests from README §Descarga, so a
# stale or tampered artifact fails here instead of inside a 45 minute suite.
# Skips work when the verified inner JAR is already present (CI cache hit).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p downloads

BUNDLE_URL="${SERVER_JAR_URL:-https://piston-data.mojang.com/v1/objects/33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c/server.jar}"
BUNDLE_SHA1="${SERVER_JAR_SHA1:-33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c}"
INNER_SHA256="${INNER_JAR_SHA256:-a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6}"

if [ -f downloads/server-26.3-inner.jar ]; then
  if printf '%s  %s\n' "$INNER_SHA256" downloads/server-26.3-inner.jar | sha256sum -c - >/dev/null 2>&1; then
    echo "inner JAR already present and verified: downloads/server-26.3-inner.jar"
    exit 0
  fi
  echo "inner JAR present but digest mismatch, re-downloading" >&2
  rm -f downloads/server-26.3-inner.jar
fi

if [ -f downloads/server-26.3.jar ] && printf '%s  %s\n' "$BUNDLE_SHA1" downloads/server-26.3.jar | sha1sum -c - >/dev/null 2>&1; then
  echo "bundle already present and verified: downloads/server-26.3.jar"
else
  echo "downloading $BUNDLE_URL"
  curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 "$BUNDLE_URL" -o downloads/server-26.3.jar
  printf '%s  %s\n' "$BUNDLE_SHA1" downloads/server-26.3.jar | sha1sum -c -
fi

python3 - <<'PY'
import pathlib, zipfile
bundle = pathlib.Path("downloads/server-26.3.jar")
inner = pathlib.Path("downloads/server-26.3-inner.jar")
with zipfile.ZipFile(bundle) as z:
    inner.write_bytes(z.read("META-INF/versions/26.3/server-26.3.jar"))
print(f"extracted {inner} ({inner.stat().st_size} bytes)")
PY

printf '%s  %s\n' "$INNER_SHA256" downloads/server-26.3-inner.jar | sha256sum -c -
