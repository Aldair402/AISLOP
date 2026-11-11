#!/usr/bin/env bash
# Toolchain efímera para esta sesión: /tmp y /var/tmp no persisten entre turnos.
# Uso: source mc-toolchain.sh   (deja cargo/rustc/java en PATH y JAVA_HOME)
set -euo pipefail
export TMPDIR="${MC_TOOLCHAIN_TMP:-/var/tmp}"
# Las raíces por defecto viven en /var/tmp (rootfs); /tmp es tmpfs (~1G) y suele
# quedarse sin espacio durante la descarga de la toolchain.
export MC_TOOLCHAIN_ROOT="${MC_TOOLCHAIN_ROOT:-/var/tmp}"
export CARGO_HOME="$MC_TOOLCHAIN_ROOT/mc-cargo"
export RUSTUP_HOME="$MC_TOOLCHAIN_ROOT/mc-rustup"
export JDK="${MC_TOOLCHAIN_JDK:-/var/tmp/mc-java25}"

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
  jdk_parent="$(dirname "$JDK")"; jdk_name="$(basename "$JDK")"
  mkdir -p "$jdk_parent"
  ( cd "$jdk_parent" \
    && curl -sSLf -o .jdk25.tar.gz \
       https://github.com/graalvm/graalvm-ce-builds/releases/download/jdk-25.0.2/graalvm-community-jdk-25.0.2_linux-x64_bin.tar.gz \
    && mkdir -p "$jdk_name" \
    && tar xzf .jdk25.tar.gz -C "$jdk_name" --strip-components=1 \
    && rm .jdk25.tar.gz )
fi

export NOPERF="${MC_TOOLCHAIN_NOPERF:-/var/tmp/mc-java25-noperf}"

if [[ ! -x "$NOPERF/bin/java" ]]; then
  bash "$(dirname "${BASH_SOURCE[0]}")/mc-aot/tools/java-no-perf-wrapper.sh" \
    "$JDK" "$NOPERF" >/dev/null
fi

export JAVA_HOME="$NOPERF"
export PATH="$CARGO_HOME/bin:$JDK/bin:$PATH"
