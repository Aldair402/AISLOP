# TickThrottler · paquete de evidencia medido por A (sin certificar)

**Rama:** `trabajo/a-06-shared-arrays` · **Fecha:** 2026-11-07 · **Procedimiento:** el mismo de
`FeatureFlagUniverse` (`analysis/c18-second-class.md`), aplicado por A y no por C.
**Estado del contador:** `count_complete` sigue en **1**. `TickThrottler` **no cuenta**: no hay
revisión de otro frente y A no se firma a sí mismo (R4 del predicado).

## Qué se midió, y cómo

Clase elegida en A-02 fase 3 (`analysis/a02-first-complete-class.md`) como la más rica de las pequeñas
del censo de 418 sin bloqueo de ejecución. Superficie declarada por el classfile oficial
(`net/minecraft/util/TickThrottler.class`, JAR `a362163e…`, clase `3c56da85…`):

| Miembro | Tipo | Medición |
|---|---|---|
| `<init>(II)V` | método (ctor público, 2 parámetros) | 80 pares (paso, umbral) en los límites de i32; identidad de clase y distinción de instancias |
| `increment()V` | método público | 720 secuencias de 1–9 incrementos, paso i32 con wrap (2³¹−1, −2³¹, negativos) contra Java 25 |
| `tick()V` | método público | 720 secuencias incremento+tick con `m > k`, `m == k`, `count <= 0` (rama `ifle`) |
| `isUnderThreshold()Z` | método público | 160 umbrales de borde: ≤ 0 (siempre cierto), `count == threshold` (falso por `if_icmpge`), por debajo y por encima |
| `incrementStep:I` · `threshold:I` · `count:I` | campos (2 `final` privados) | sin canal propio: cada uno se ejercita en los 1.680 casos anteriores |

**1.680 resultados** Java 25 vs nativo sin JVM, 0 desacuerdos; superficie reconciliada
classfile ↔ reflexión (flags, superclase `java/lang/Object`, sin interfaces, sin `<clinit>`,
modificadores por miembro); el Rust generado contiene la clase y su despacho numérico.

El **único canal observable** es `isUnderThreshold()Z`: la clase no expone accesor ni `toString`,
y no se inventa ninguno. Todo el efecto del constructor y de los tres campos fluye por ahí; si
`isUnderThreshold()Z` tradujera mal, los siete miembros fallarían a la vez. Está declarado en
`cross_dependencies` del informe, no escondido. Esto limita lo que el paquete puede demostrar:
igualdad en los 1.680 casos medidos, no equivalencia universal; y nada sobre publicación entre
hilos (la clase no se comparte entre hilos en ningún caso medido).

## Qué falta para que cuente

1. **Revisión de otro frente** (B o C): el predicado hoy da `review-required`
   (`no-review`, `no-reviewer`, `not-certified`) — veredicto honesto, sin firma.
2. Nada más: la superficie, la evidencia y las limitaciones están declaradas y regenerables
   (`update-class-evidence.py --spec analysis/class-specs/tickthrottler.json --check`).

## Qué cambió para que esto exista

- `mc-aot/tests/check-tickthrottler-class-surface.py` (nuevo) — el arnés por miembro.
- `analysis/class-specs/tickthrottler.json` — el spec para el regenerador.
- `analysis/tickthrottler-static-surface.log` · `analysis/class-evidence/tickthrottler{,-classfile}.json`
  · `analysis/tickthrottler-evidence-report.json` — evidencia regenerable.
- `analysis/class-registry.json` — entrada `partial-evidence` (medida, sin revisar).
- `mc-aot/run-regressions.sh` — etapas `check-tickthrottler-{class-surface,evidence-audit,evidence-fresh}`.
- CI `quick` — auditoría de manifiesto y frescura de evidencia (espejo de FFU).

Límites del paquete: la salida por caso es un bit; no cubre secuencias arbitrarias ni repeticiones
más allá de 9 por caso; no mide concurrencia. La clase sigue sin contar para el objetivo de
3.881/7.762.
