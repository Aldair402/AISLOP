# Opt-in unificado de futuros: decisión 2026-11-07 (`restricted`)

**Decide:** A (dueño del opt-in desde Q-AC-7), tras la respuesta de B en Q-AB-2/504994b y el acuerdo C–A–B vigilado por `check-futures-optin-shared.py`.
**Estado del código:** mitad de A integrada en `trabajo/a-06-shared-arrays`; la mitad de B vive en `trabajo/b-01-contrato-futures` y **no está integrada en `main`**. El PR conjunto del 2026-11-07 no puede cerrar solo con los medios de A; este documento fija la decisión y la evidencia.

## Decisión

El valor canónico de `MC_AOT_FUTURES` es **`restricted`**.

- Describe un perfil, no una caducidad: todos los futuros tan restringidos como el completion-only (completados normalmente, identidad, consultas, sin cancelación/excepciones observables).
- Es el valor que B ya implementa en `futures_restricted_optin()` (`504994b`, rama `b-01`), con `off` y `completed-only` admitidos en el mismo `match`.
- Motivo de no mantener `completed-only` como canónico: B lo aceptaría como alias, pero nombrarlo canónico contradiría su mensaje literal y dividiría a quien lea cualquiera de los dos backends.

## Semántica resultante (ambos backends)

| Valor | Perfil | Notas |
|---|---|---|
| `restricted` | habilitado | **canónico**. En B además habilita futuros pendientes (`futures_pending_optin`); el backend principal monohilo no modela pendientes, solo completados |
| `completed-only` | habilitado | alias histórico del mismo perfil (el nombre que A publicó en su día); se conserva por una versión en ambos backends |
| `off` | apagado | explícito en ambos |
| otra cosa | error | rechazado con mensaje literal, nunca adivinado. A: `MC_AOT_FUTURES: valor no soportado: … (admitidos: restricted, completed-only, off)` |
| no definida | alias heredado | A: `MC_AOT_NUMERIC_COMPLETED_FUTURE=1`. B: `MC_AOT_RAYON_COMPLETED_FUTURE=1` |
| vacía | como no definida | solo en A; B trata `Ok("")` como error (admitido documentado, no interceptado) |

La habilitación no es «de adorno»: sin opt-in, el backend numérico se detiene al compilar `completedFuture` con un literal de guarda; con `restricted` compila el mismo perfil que contrastaba antes. Verificado: `check-numeric-completed-future.py` (90 resultados Java 25/nativo, exit 0) con `restricted` solo, `completed-only` solo, `off`, alias heredado y valor desconocido rechazado.

## Evidencia del acuerdo (2026-11-07, máquina de A)

- **En `main` (sin B-01 integrado):** `check-futures-optin-shared.py` imprime `PENDIENTE` (el vendor concurrente no declara opt-in propio) y sale 0. Es el estado real en `main` tras `c1357f7`; no se presenta como unificado.
- **Vendor de B presente (árbol simulado en `/tmp/guard-sim`, `src/concurrent_compile.rs` de `origin/trabajo/b-01-contrato-futures`, tal cual):** el guarda imprime `A acepta: ['completed-only', 'off', 'restricted']`, `B acepta: ['completed-only', 'off', 'restricted']`, `OK … el opt-in unificado existe de verdad.` (exit 0), con AVISO de varios comunes — esperable mientras sobreviva `completed-only` como alias; el canónico es único: `restricted`.
- `check-integration-contract.py` (A-01) re-pasa con D12 actualizada («D12 describe el estado real del opt-in», contador incluido).

## Qué falta para decir «unificado en `main`»

1. C integra la rama `b-01` en `main`/`qa-all-agents` (revisión cruzada de B, Q-BC-8 cerrado).
2. El guarda entonces compara de verdad en CI y en cada integral; hasta entonces cualquier verde del guarda sobre `main` es **PENDIENTE**, no «unificado».
3. Una versión de gracia para `completed-only` y los alias heredados, con fecha de retirada acordada con B y C.
4. B publica en el hilo A–B cuándo `restricted` migra a "habilitado" en `futures_pending_optin` (ya sucede) para que la documentación operatoria no sugiera que apaga pendientes.

**Límites declarados:** este documento no fusiona `b-01` en `main`, no certifica `B-03`, no implementa excepciones ni cancelación efectiva, no toca `Main`. El perfil sigue siendo solo futuros completados normalmente en el backend principal.
