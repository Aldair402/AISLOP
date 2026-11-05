#!/usr/bin/env bash
# C-07: Isolated Main probe — does not accept EULA, does not open ports.
# Usage: bash mc-aot/tools/main-probe.sh [output_log]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMPDIR="${TMPDIR:-/tmp}"
WORK="$(mktemp -d "$TMPDIR/mc-main-probe.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
LOG="${1:-$ROOT/analysis/main-probe-$(date +%Y%m%d-%H%M%S).log}"
JAR="$ROOT/downloads/server-26.3-inner.jar"
if [[ ! -f "$JAR" ]]; then echo "Missing $JAR — run README Preparation first" >&2; exit 2; fi
: "${JAVA_HOME:?Define JAVA_HOME to JDK 25}"
echo "==> C-07 Main probe — isolated, no EULA accept, no ports" | tee "$LOG"
echo "WORK=$WORK" | tee -a "$LOG"
echo "JAR_SHA256=$(sha256sum "$JAR" | cut -d' ' -f1)" | tee -a "$LOG"
echo "JAVA=$JAVA_HOME/bin/java $($JAVA_HOME/bin/java -version 2>&1 | head -n1)" | tee -a "$LOG"
echo "RUST=$(rustc --version 2>&1 || echo 'no rust')" | tee -a "$LOG"
# Clean old binaries that could be mistaken for success
rm -f "$ROOT/mc-aot/target/debug/mc-aot" "$WORK/native-main" 2>/dev/null || true
# Record config and attempt compilation to native (does not run server)
set +e
cargo run --quiet --manifest-path "$ROOT/mc-aot/Cargo.toml" -- probe-main "$JAR" "$WORK/native-main" >"$WORK/compile.log" 2>&1
COMPILE_EXIT=$?
set -e
cat "$WORK/compile.log" | tee -a "$LOG"
echo "compile_exit=$COMPILE_EXIT" | tee -a "$LOG"
if [[ $COMPILE_EXIT -eq 0 && -f "$WORK/native-main" ]]; then
  echo "Binary produced at $WORK/native-main — NOT executing (would require EULA and ports)" | tee -a "$LOG"
  echo "To manually test startup cycle (after C-07, requires approval):" | tee -a "$LOG"
  echo "  mkdir -p $WORK/server && echo 'eula=false' > $WORK/server/eula.txt" | tee -a "$LOG"
  echo "  $WORK/native-main --nogui --world $WORK/server --port 25565 (must remain closed by default)" | tee -a "$LOG"
else
  echo "No binary — blocker is expected until ForkJoinPool/TracingExecutor resolved (see analysis/main-completed-future-attempt.log)" | tee -a "$LOG"
  echo "First blocker: $(grep -m1 'Error: new no soportado' "$WORK/compile.log" || echo 'unknown')" | tee -a "$LOG"
fi
# Never accept EULA automatically, never open ports
echo "==> Probe finished, workdir will be removed, log at $LOG" | tee -a "$LOG"
echo "Check: grep compile_exit $LOG && ls -l $LOG"
