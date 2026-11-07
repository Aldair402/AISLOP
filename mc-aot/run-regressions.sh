#!/usr/bin/env bash
# Pruebas y auditorías reproducibles; no certifican clases completas ni el servidor.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${JAVA_HOME:?Define JAVA_HOME apuntando a un JDK 25}"
mkdir -p "$ROOT/analysis"
run_logged() {
  local name="$1"; shift
  echo "==> $name"
  if ! "$@" >"$ROOT/analysis/$name-latest.log" 2>&1; then
    tail -n 50 "$ROOT/analysis/$name-latest.log" >&2
    return 1
  fi
}
cd "$ROOT"
run_logged cargo-test cargo test --manifest-path mc-aot/Cargo.toml
run_logged build-examples bash mc-aot/build-examples.sh
# El oráculo recorre todas las parejas Latin-1 x BMP, sin depender de archivos .class en el workspace.
oracle_dir="$(mktemp -d "${TMPDIR:-/tmp}/mc-case-oracle.XXXXXX")"
trap 'rm -rf "$oracle_dir"' EXIT
run_logged casefold-oracle-compile "$JAVA_HOME/bin/javac" -d "$oracle_dir" mc-aot/tools/CaseFoldOracleJava25.java
run_logged casefold-oracle "$JAVA_HOME/bin/java" -cp "$oracle_dir" CaseFoldOracleJava25
for test in check-guards check-index check-inspect check-graph check-wide check-numeric-stack check-dup-x check-numeric-guards check-object check-multi check-reference check-static-demo check-static-constants check-static-guards check-string-main check-string-guards check-exceptions check-exception-static check-exception-table check-nbt-exceptions check-multi-static check-multi-static-guards check-static-references check-static-string-constant check-static-array-types check-multi-objects check-multi-object-init check-multi-object-guards check-multi-init-errors check-bundle-libraries check-static-float-preparation check-multi-volatile check-multi-interfaces check-jdk-collections check-jdk-threadlocal check-jdk-inheritable-local check-jdk-properties check-ascii-ignore-case check-unicode-ignore-case check-classloader-identity check-reflection-catches check-object-arrays check-string-format-basic check-final-enums check-real-slf4j-enums check-system-streams check-stringbuilder check-monitors check-jdk-arraylist check-arraylist-iterator check-iterable-arraylist check-interface-dispatch check-class-names check-real-slf4j-service check-service-loader check-security-manager-java25 check-security-dead-code check-multirelease-classpath check-classloader-load check-reflection-constructors check-reflection-methods check-project-casts check-stacktrace-guard check-linkedhashset check-loader-dead-code check-static-binder-resources check-map-values check-default-interface-init check-multi-recursion check-queue-drain-boolean check-inherited-static check-inherited-objects check-exception-cause check-arrays-as-list check-stackwalker-caller check-class-assignable check-securitymanager-subclass check-indy-concat check-duration-parse check-assertion-status check-string-trim check-string-lower-ascii check-boxing-valueof check-atomic-reference check-stateless-lambda check-float-double check-identity-formatter check-startup-primitives check-map-compute check-threadlocal-supplier check-empty-jdk-arrays check-external-exception-statics check-cross-package-dispatch check-external-exception-catch check-version-resource check-version-reader check-immutable-empties check-formatting-profile check-startup-extensions check-gson-exceptions check-real-abbreviation-map check-jfr-disabled-profile check-startup-collections check-timing-atomic check-lambda-discard check-mth-math-profile check-runtime-profile check-real-standardlevel check-root-uppercase check-real-log4j-properties check-reentrant-locks check-concurrent-linked-queue check-system-arraycopy check-files-profile check-path-queries check-file-properties check-file-properties-fuzz check-real-eula-isolated check-synchronized-method check-uri-commonlinks check-cross-package-public check-hashset-profile check-concurrent-int-demo check-concurrent-quartpos check_real_methods; do
  run_logged "$test" python3 "mc-aot/tests/$test.py"
done
run_logged check-real-tracing-shutdown python3 mc-aot/tests/check-real-tracing-shutdown.py
run_logged check-real-tracy-thread-name python3 mc-aot/tests/check-real-tracy-thread-name.py
run_logged check-real-util-worker-guards python3 mc-aot/tests/check-real-util-worker-guards.py
run_logged check-real-util-worker-onstart python3 mc-aot/tests/check-real-util-worker-onstart.py
run_logged check-quartpos-class-surface python3 mc-aot/tests/check-quartpos-class-surface.py
run_logged check-class-surface-evidence python3 mc-aot/tests/check-class-surface-evidence.py
run_logged check-classfile-surface python3 mc-aot/tools/classfile-surface.py net.minecraft.core.QuartPos --registry analysis/class-registry.json
run_logged check-quartpos-evidence-audit python3 mc-aot/tools/class-surface-evidence.py analysis/class-evidence/quartpos.json
run_logged check-quartpos-evidence-fresh python3 mc-aot/tools/update-quartpos-evidence.py --check
run_logged check-class-registry python3 mc-aot/tools/check-class-registry.py
run_logged check-family-partition python3 mc-aot/tools/check-family-partition.py
run_logged c01-baseline-exists test -f analysis/c01-baseline-2026-11-05.md
run_logged check-enum-valueof-profile python3 mc-aot/tests/check-enum-valueof-profile.py
run_logged check-enum-valueof-cache python3 mc-aot/tests/check-enum-valueof-cache.py
run_logged check-real-minecraft-enum-valueof python3 mc-aot/tests/check-real-minecraft-enum-valueof.py
run_logged check-numeric-object-sharing python3 mc-aot/tests/check-numeric-object-sharing.py
run_logged check-numeric-shared-references python3 mc-aot/tests/check-numeric-shared-references.py
run_logged check-numeric-shared-monitors python3 mc-aot/tests/check-numeric-shared-monitors.py
run_logged check-numeric-concurrent-bridge python3 mc-aot/tests/check-numeric-concurrent-bridge.py
run_logged check-numeric-concurrent-graph python3 mc-aot/tests/check-numeric-concurrent-graph.py
run_logged check-numeric-concurrent-graph-ticktask python3 mc-aot/tests/check-numeric-concurrent-graph.py --ticktask
run_logged check-numeric-bridge-layout python3 mc-aot/tests/check-numeric-bridge-layout.py
run_logged check-numeric-wide-slots python3 mc-aot/tests/check-numeric-wide-slots.py
run_logged check-vanilla-layout-profile python3 mc-aot/tests/check-vanilla-layout-profile.py
run_logged check-numeric-auto-publish python3 mc-aot/tests/check-numeric-auto-publish.py
run_logged check-numeric-shared-arrays python3 mc-aot/tests/check-numeric-shared-arrays.py
run_logged check-rayon-completed-future python3 mc-aot/tests/check-rayon-completed-future.py
run_logged check-rayon-shared-completed-future python3 mc-aot/tests/check-rayon-shared-completed-future.py
run_logged check-numeric-completed-future python3 mc-aot/tests/check-numeric-completed-future.py
run_logged check-real-chunk-passthrough-future python3 mc-aot/tests/check-real-chunk-passthrough-future.py
run_logged check-completable-future-oracle python3 mc-aot/tests/check-completable-future-oracle.py
run_logged check-forkjoin-handler-oracle python3 mc-aot/tests/check-forkjoin-handler-oracle.py
run_logged check-rayon-java-pool-queries python3 mc-aot/tests/check-rayon-java-pool-queries.py
run_logged check-rayon-pending-future python3 mc-aot/tests/check-rayon-pending-future.py
run_logged check-futures-contract python3 mc-aot/tests/check-futures-contract.py
run_logged check-executor-inventory python3 mc-aot/tests/check-executor-inventory.py
run_logged check-shared-worker-bytecode python3 mc-aot/tests/check-shared-worker-bytecode.py
run_logged check-real-util4-shared-worker python3 mc-aot/tests/check-real-util4-shared-worker.py
run_logged check-real-ticktask-shared-worker python3 mc-aot/tests/check-real-ticktask-shared-worker.py
run_logged check-hashset-class-keys python3 mc-aot/tests/check-hashset-class-keys.py
run_logged check-abstract-spliterator-profile python3 mc-aot/tests/check-abstract-spliterator-profile.py
run_logged check-stream-support-profile python3 mc-aot/tests/check-stream-support-profile.py
run_logged check-class-forname-osgi python3 mc-aot/tests/check-class-forname-osgi.py
run_logged check-real-log4j-safestream python3 mc-aot/tests/check-real-log4j-safestream.py
run_logged check-runtime-permission python3 mc-aot/tests/check-runtime-permission.py
run_logged check-boolean-supplier python3 mc-aot/tests/check-boolean-supplier.py
run_logged check-privileged-action python3 mc-aot/tests/check-privileged-action.py
run_logged check-classloader-array python3 mc-aot/tests/check-classloader-array.py
run_logged check-system-classloader python3 mc-aot/tests/check-system-classloader.py
run_logged check-log4j-provider-resource python3 mc-aot/tests/check-log4j-provider-resource.py
run_logged check-url-openstream-guard python3 mc-aot/tests/check-url-openstream-guard.py
run_logged check-duration-pattern-profile python3 mc-aot/tests/check-duration-pattern-profile.py
run_logged check-weak-loader-reference python3 mc-aot/tests/check-weak-loader-reference.py
run_logged check-file-not-found-exception python3 mc-aot/tests/check-file-not-found-exception.py
run_logged check-linkedhashset-capacity python3 mc-aot/tests/check-linkedhashset-capacity.py
run_logged check-concurrent-keyset-profile python3 mc-aot/tests/check-concurrent-keyset-profile.py
run_logged check-set-add-method-reference python3 mc-aot/tests/check-set-add-method-reference.py
run_logged check-printstream-construction-guard python3 mc-aot/tests/check-printstream-construction-guard.py
run_logged check-reflection-declared-constructors python3 mc-aot/tests/check-reflection-declared-constructors.py
run_logged check-class-forname-loader python3 mc-aot/tests/check-class-forname-loader.py
run_logged check-class-as-subclass python3 mc-aot/tests/check-class-as-subclass.py
run_logged check-comparator-comparing-guard python3 mc-aot/tests/check-comparator-comparing-guard.py
run_logged check-arraylist-stream-profile python3 mc-aot/tests/check-arraylist-stream-profile.py
run_logged check-arraylist-stream-max python3 mc-aot/tests/check-arraylist-stream-max.py
run_logged check-stream-sorted-profile python3 mc-aot/tests/check-stream-sorted-profile.py
run_logged check-stream-map-profile python3 mc-aot/tests/check-stream-map-profile.py
run_logged check-collectors-joining-profile python3 mc-aot/tests/check-collectors-joining-profile.py
run_logged check-arraylist-stream-joining python3 mc-aot/tests/check-arraylist-stream-joining.py
run_logged check-optional-or-else-get python3 mc-aot/tests/check-optional-or-else-get.py
run_logged check-current-thread-interrupt python3 mc-aot/tests/check-current-thread-interrupt.py
run_logged check-concurrentmap-cast python3 mc-aot/tests/check-concurrentmap-cast.py
run_logged check-current-time-millis python3 mc-aot/tests/check-current-time-millis.py
run_logged check-properties-entryset-empty python3 mc-aot/tests/check-properties-entryset-empty.py
run_logged check-treemap-entry-key python3 mc-aot/tests/check-treemap-entry-key.py
run_logged check-lambda-class-adaptation python3 mc-aot/tests/check-lambda-class-adaptation.py
run_logged check-object-equals-profile python3 mc-aot/tests/check-object-equals-profile.py
run_logged check-charsequence-project-class python3 mc-aot/tests/check-charsequence-project-class.py
run_logged check-current-thread-id python3 mc-aot/tests/check-current-thread-id.py
run_logged check-stackwalker-walk-prefix python3 mc-aot/tests/check-stackwalker-walk-prefix.py
run_logged check-optional-map python3 mc-aot/tests/check-optional-map.py
run_logged check-real-log4j-stacklocator python3 mc-aot/tests/check-real-log4j-stacklocator.py
run_logged check-charsequence-tostring python3 mc-aot/tests/check-charsequence-tostring.py
run_logged check-log4j-property-patterns python3 mc-aot/tests/check-log4j-property-patterns.py
run_logged check-root-lowercase python3 mc-aot/tests/check-root-lowercase.py
run_logged check-set-stream-profile python3 mc-aot/tests/check-set-stream-profile.py
run_logged check-comparator-project-class python3 mc-aot/tests/check-comparator-project-class.py
run_logged check-lambda-private-special python3 mc-aot/tests/check-lambda-private-special.py
run_logged check-objects-nonnull-methodref python3 mc-aot/tests/check-objects-nonnull-methodref.py
run_logged check-context-classloader python3 mc-aot/tests/check-context-classloader.py
run_logged check-objects-tostring-default python3 mc-aot/tests/check-objects-tostring-default.py
run_logged check-builder-append-charsequence python3 mc-aot/tests/check-builder-append-charsequence.py
run_logged check-builder-capacity-lifecycle python3 mc-aot/tests/check-builder-capacity-lifecycle.py
run_logged check-builder-capacity python3 mc-aot/tests/check-builder-capacity.py
run_logged check-builder-double-guard python3 mc-aot/tests/check-builder-double-guard.py
run_logged check-character-cast python3 mc-aot/tests/check-character-cast.py
run_logged check-character-upper-char python3 mc-aot/tests/check-character-upper-char.py
run_logged check-charsequence-cast python3 mc-aot/tests/check-charsequence-cast.py
run_logged check-charsequence-subsequence python3 mc-aot/tests/check-charsequence-subsequence.py
run_logged check-class-isarray python3 mc-aot/tests/check-class-isarray.py
run_logged check-collection-cast python3 mc-aot/tests/check-collection-cast.py
run_logged check-date-cast python3 mc-aot/tests/check-date-cast.py
run_logged check-date-instant-roundtrip python3 mc-aot/tests/check-date-instant-roundtrip.py
run_logged check-double-boxing python3 mc-aot/tests/check-double-boxing.py
run_logged check-formatter-formatto-guard python3 mc-aot/tests/check-formatter-formatto-guard.py
run_logged check-math-add-exact python3 mc-aot/tests/check-math-add-exact.py
run_logged check-primitive-array-class-literals python3 mc-aot/tests/check-primitive-array-class-literals.py
run_logged check-short-boxing python3 mc-aot/tests/check-short-boxing.py
run_logged check-simpledateformat-guard python3 mc-aot/tests/check-simpledateformat-guard.py
run_logged check-stackframe-classname python3 mc-aot/tests/check-stackframe-classname.py
run_logged check-stackframe-element-guard python3 mc-aot/tests/check-stackframe-element-guard.py
run_logged check-stacktraceelement-cast python3 mc-aot/tests/check-stacktraceelement-cast.py
run_logged check-stackwalker-dropwhile python3 mc-aot/tests/check-stackwalker-dropwhile.py
run_logged check-string-last-index python3 mc-aot/tests/check-string-last-index.py
run_logged check-temporal-cast python3 mc-aot/tests/check-temporal-cast.py
run_logged check-version-split-profile python3 mc-aot/tests/check-version-split-profile.py
run_logged check-weakhashmap-guard python3 mc-aot/tests/check-weakhashmap-guard.py
run_logged check-arrays-copyof-refs python3 mc-aot/tests/check-arrays-copyof-refs.py
run_logged check-builder-append-charsequence-range python3 mc-aot/tests/check-builder-append-charsequence-range.py
run_logged check-bytearrayinputstream-profile python3 mc-aot/tests/check-bytearrayinputstream-profile.py
run_logged check-character-whitespace-char python3 mc-aot/tests/check-character-whitespace-char.py
run_logged check-classloader-parent python3 mc-aot/tests/check-classloader-parent.py
run_logged check-collections-emptyset python3 mc-aot/tests/check-collections-emptyset.py
run_logged check-context-classloader-set python3 mc-aot/tests/check-context-classloader-set.py
run_logged check-hashmap-capacity python3 mc-aot/tests/check-hashmap-capacity.py
run_logged check-identity-hashcode-guard python3 mc-aot/tests/check-identity-hashcode-guard.py
run_logged check-identity-map-set-profile python3 mc-aot/tests/check-identity-map-set-profile.py
run_logged check-integer-hex-string python3 mc-aot/tests/check-integer-hex-string.py
run_logged check-reflection-member-cast python3 mc-aot/tests/check-reflection-member-cast.py
run_logged check-string-contains-sequence python3 mc-aot/tests/check-string-contains-sequence.py
run_logged check-threadfactory-guard python3 mc-aot/tests/check-threadfactory-guard.py
run_logged check-timeunit-conversion python3 mc-aot/tests/check-timeunit-conversion.py
run_logged check-uri-cast python3 mc-aot/tests/check-uri-cast.py
run_logged check-uri-path-profile python3 mc-aot/tests/check-uri-path-profile.py
run_logged check-uri-scheme-profile python3 mc-aot/tests/check-uri-scheme-profile.py
run_logged check-uri-syntax-exception python3 mc-aot/tests/check-uri-syntax-exception.py
run_logged check-url-touri-guard python3 mc-aot/tests/check-url-touri-guard.py
run_logged check-reflection-member-modifiers python3 mc-aot/tests/check-reflection-member-modifiers.py
run_logged check-reflection-modifier-bits python3 mc-aot/tests/check-reflection-modifier-bits.py
run_logged check-class-modifiers python3 mc-aot/tests/check-class-modifiers.py
run_logged check-accessible-object-guard python3 mc-aot/tests/check-accessible-object-guard.py
run_logged check-internal-error-profile python3 mc-aot/tests/check-internal-error-profile.py
run_logged check-string-tochararray python3 mc-aot/tests/check-string-tochararray.py
run_logged check-arrays-sort-char python3 mc-aot/tests/check-arrays-sort-char.py
run_logged check-class-limit-option python3 mc-aot/tests/check-class-limit-option.py
run_logged check-matcher-matches-guard python3 mc-aot/tests/check-matcher-matches-guard.py
run_logged log4rs-prototype-cargo-test cargo test --locked --manifest-path mc-aot/log4rs-prototype/Cargo.toml
run_logged check-log4rs-prototype python3 mc-aot/tests/check-log4rs-prototype.py
run_logged check-log4rs-eula-event python3 mc-aot/tests/check-log4rs-eula-event.py
run_logged check-minecraft-log-config-oracle python3 mc-aot/tests/check-minecraft-log-config-oracle.py
run_logged check-eula-throwable-oracle python3 mc-aot/tests/check-eula-throwable-oracle.py
run_logged check-rayon-java-worker-lifecycle python3 mc-aot/tests/check-rayon-java-worker-lifecycle.py
run_logged check-rayon-java-forkjoin python3 mc-aot/tests/check-rayon-java-forkjoin.py
run_logged check-rayon-java-captured-object python3 mc-aot/tests/check-rayon-java-captured-object.py
run_logged check-rayon-real-ticktask-capture python3 mc-aot/tests/check-rayon-real-ticktask-capture.py
run_logged check-rayon-forkjoin-profile python3 mc-aot/tests/check-rayon-forkjoin-profile.py
run_logged check-concurrent-int-rayon env MC_AOT_CONCURRENT_BACKEND=concurrent-rayon-int-demo python3 mc-aot/tests/check-concurrent-int-demo.py
run_logged check-concurrent-quartpos-rayon env MC_AOT_CONCURRENT_BACKEND=concurrent-rayon-int-demo python3 mc-aot/tests/check-concurrent-quartpos.py
run_logged real-slf4j-initialize python3 mc-aot/tools/probe-real-slf4j-initialize.py
for test in compare-mth compare-switch compare-small-args compare-long compare-arrays compare-map-array compare-object compare-multi compare-reference compare-combined compare-static-init compare-multi-static-init compare-static-arrays compare-real-multi-objects compare-strings compare-neighbor-exception; do
  run_logged "$test" python3 "graal-test/$test.py"
done
for test in audit audit-small-args audit-long audit-arrays audit-objects audit-references audit-static-init audit-multi-static audit-static-references audit-strings audit-exceptions; do
  run_logged "$test" python3 "mc-aot/$test.py"
done
for test in sweep-long sweep-arrays sweep-references sweep-static-init sweep-multi-static sweep-static-references sweep-static-float-preparation; do
  run_logged "$test" python3 "graal-test/$test.py"
done
echo 'Todas las regresiones terminaron correctamente. Ninguna certifica el servidor completo.'
