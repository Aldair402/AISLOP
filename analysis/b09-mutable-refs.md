# B-09 — Referencias mutables en el backend concurrente

**Rama:** `trabajo/b-01-contrato-futures` · **Commit:** `adb04d9` · **Fecha:** 2026-11-05
**Origen:** [`Q-AB-1`](discussion/threads/a-b.md) — A preguntó si B admitía campos de referencia no `final` en el
backend de Rayon, porque hoy una clase como `Node { int value; Node next; }` se traduce en el backend monohilo y no
en el concurrente.
**Opt-in:** `MC_AOT_RAYON_MUTABLE_REFS=1` (además de `MC_AOT_RAYON_PROJECT_REFERENCES=1`, que ya era necesario).

## 1. Qué se admitió y qué no

| Caso | Antes | Ahora (con el opt-in) |
|---|---|---|
| Campo de referencia no `final` de una clase del proyecto | rechazado (`captura de referencia debe ser final`) | **admitido** |
| Escritura de ese campo fuera del constructor | rechazada en traducción | **admitida**, con comprobación de destino |
| Lectura de ese campo desde cualquier hilo | — | admitida (mutex del heap) |
| Campo de referencia `final` escrito fuera del constructor | rechazado | **sigue rechazado** |
| Campo de referencia de una clase no modelada | rechazado | **sigue rechazado** |
| Clase contenedora no `final`, con `<clinit>` o con jerarquía | rechazada | **sigue rechazada** |
| Sin el opt-in | rechazo | **rechazo**, literal y verificado |

## 2. Reglas de la escritura

1. **Una sola vía:** `heap.write`, que toma el mutex del heap. No hay escritura directa desde un worker ni
   publicación con el monitor retenido alrededor del mutex.
2. **Orden de adquisición:** monitor del objeto primero; operación del heap dentro (su mutex es hoja). El orden
   inverso no existe en el código generado y no está admitido (acordado con A en `Q-AB-1`).
3. **Destino comprobado en ejecución:** el valor debe ser `null` o un objeto publicado de la clase declarada por el
   campo. Cualquier otra cosa aborta con diagnóstico; no hay escritura a medias ni coerción silenciosa.
4. **Tipado del campo:** se conserva el mismo control que ya existía para referencias (`referencia de campo no
   soportada`).

## 3. Qué se garantiza y qué no

**Se garantiza** (probado): que la escritura es atómica bajo el mutex del heap, que el valor observado después es el
último escrito, que un campo `final` no se escribe nunca fuera del constructor y que los invariantes de la cadena se
mantienen bajo concurrencia.

**No se garantiza:** el *happens-before* del modelo de memoria de Java, ni el orden en que las escrituras de varios
workers se hacen visibles. Por eso el perfil es opt-in, y por eso la evidencia se presenta como «estos invariantes se
cumplen», nunca como «equivalente a Java». Es exactamente la diferencia que el proyecto prohíbe disimular.

## 4. Evidencia

| Prueba | Resultado |
|---|---|
| `mc-aot/tests/check-rayon-mutable-refs.py` | **84 resultados** Java 25/Rayon: 28 valores por fixture, dos fixtures (mutables y control con `final`), más dos guardas |
| Control con campo `final`, sin opt-in | compila y coincide con Java: el opt-in no cambia el camino ya soportado |
| Guarda sin `MC_AOT_RAYON_MUTABLE_REFS` | rechazo literal `concurrent-int: captura de referencia debe ser final`, sin binario generado |
| Guarda sin `MC_AOT_RAYON_PROJECT_REFERENCES` | no hay traducción de clases del proyecto |
| `relink_under_monitor_keeps_the_chain_whole` (`mc-aot/tests/rayon_stress.rs`) | 20 rondas × 4 workers × 100 reenlaces sobre 64 nodos: ningún nodo perdido, valores intactos, recorrido exacto de 64 nodos y sin ciclos, con perro guardián anti-bloqueo |
| `cargo test` | 66 + 32 + 34 + 32 + 34 = **198 pruebas, 0 fallos** |
| Contrato B-01 | **86 casos** (24 diferenciales, 21 guardas, 22 unitarias, 11 solo-Java, 8 sin modelar) |

Log de la validación focalizada: `analysis/check-rayon-mutable-refs-validation.log`.

## 5. Lo que esta tarea **no** hace

- No admite **métodos** que devuelvan referencias del proyecto (`()Lnet/minecraft/...;` sigue fuera del perfil):
  la prueba tuvo que leer el campo directamente (`a.next.read()`) en vez de llamar a un `step()`. Es el límite que
  aparecería primero al traducir una lista enlazada real, y es una tarea aparte.
- No admite constructores con firma mixta `(ILnet/minecraft/...;)V`; el fixture de control usa `Node(Node)` y asigna
  el `int` después.
- No implementa `wait`/`notify`, ni publica automáticamente objetos creados por workers (sigue siendo el `PublishSink`
  de A para el backend numérico).

## 6. Para A y C

- **A:** el orden acordado está implementado tal cual; si en `numeric_concurrent_graph_bridge.inc` el orden fuera el
  inverso en algún camino, ese camino no está cubierto por esta evidencia y conviene que lo digas en el hilo.
- **C:** falta la entrada en `run-regressions.sh` confirmada y el `review` de la tarea; el script ya está registrado
  junto a las demás pruebas de B.
