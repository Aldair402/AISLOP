#!/usr/bin/env bash
# Toolchain efímera para esta sesión: /tmp y /var/tmp no persisten entre turnos.
# Uso: source mc-toolchain.sh   (deja cargo/rustc/java en PATH y JAVA_HOME)
set -euo pipefail
export TMPDIR=/var/tmp
export CARGO_HOME=/tmp/mc-cargo
export RUSTUP_HOME=/tmp/mc-rustup
export JDK=/var/tmp/mc-java25

if [[ ! -x "$CARGO_HOME/bin/cargo" ]]; then
  mkdir -p "$RUSTUP_HOME"
  curl -sSf https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init \
    -o "$RUSTUP_HOME/rustup-init"
  chmod +x "$RUSTUP_HOME/rustup-init"
  "$RUSTUP_HOME/rustup-init" -y --no-modify-path --profile minimal --default-toolchain stable \
    >/tmp/rustup.log 2>&1 || true
  "$CARGO_HOME/bin/rustup" default stable >/dev/null 2>&1 || true
fi

if [[ ! -x "$JDK/bin/javac" ]]; then
  ( cd /var/tmp \
    && curl -sSLf -o jdk25.tar.gz \
       https://github.com/graalvm/graalvm-ce-builds/releases/download/jdk-25.0.2/graalvm-community-jdk-25.0.2_linux-x64_bin.tar.gz \
    && mkdir -p mc-java25 \
    && tar xzf jdk25.tar.gz -C mc-java25 --strip-components=1 \
    && rm jdk25.tar.gz )
fi

if [[ ! -x /var/tmp/mc-java25-noperf/bin/java ]]; then
  bash "$(dirname "${BASH_SOURCE[0]}")/mc-aot/tools/java-no-perf-wrapper.sh" \
    "$JDK" /var/tmp/mc-java25-noperf >/dev/null
fi

export JAVA_HOME=/var/tmp/mc-java25-noperf
export PATH="$CARGO_HOME/bin:$JDK/bin:$PATH"
