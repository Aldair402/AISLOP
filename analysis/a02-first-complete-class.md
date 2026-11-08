# A-02 fase 3 · primera clase vanilla completa (plan medido)

Fecha: 2026-11-07. Rama: `trabajo/a-06-shared-arrays`.

## Por qué este paso y no otro

Las ranuras de los ocho primitivos (paso cerrado el 2026-11-06) subieron el censo a
**2.611 describibles / 1.564 con campos / 4.048 campos**, pero siguen **0 clases traducidas
y ejecutadas de 7.762**. Ampliar el perfil otra vez (tipos del JAR de librería, 2.238 clases)
subiría un número descriptivo sin mover el de ejecución. El criterio del usuario es
**clases completas**, no métodos sueltos ni layouts.

Por eso el siguiente paso es el contrario: dejar de crecer el perfil y **traducir y ejecutar
una clase vanilla entera**, con todas sus declaraciones (constructor y todos los métodos),
comparada contra Java 25.

## Candidatas, medidas sobre el JAR oficial

Intersección de dos censos ya existentes, ambos reproducibles:

1. `layout-profile-census.py`: describible y **sin bloqueo de ejecución** (sin campos
   estáticos, sin `<clinit>`, sin interfaces) → **418 clases**.
2. Barrido `javap -p -c` de esas 418: recuento de instrucciones, número de métodos y
   referencias constantes externas → `/var/tmp/scan418.json` (script en el propio análisis).

Candidatas con cero referencias externas fuera de `java/lang/Object` y sin `invokedynamic`:

| Clase | Instrucciones | Métodos | Nota |
|---|---:|---:|---|
| `net/minecraft/util/TickThrottler` | 39 | 4 | 3 campos `int` (2 `final`), constructor, `increment()V`, `tick()V`, `isUnderThreshold()Z` |
| `net/minecraft/world/level/block/entity/BeaconBeamOwner$Section` | 22 | 4 | campos `int` |
| `net/minecraft/world/entity/ai/behavior/PrepareRamNearestTarget$RamCandidate` | 21 | 4 | campos `int` |
| `net/minecraft/commands/arguments/selector/options/SetOnceOptionState` | 14 | 3 | 1 campo `boolean`, ramas triviales |

**Elegida: `net/minecraft/util/TickThrottler`.** Es la más rica de las pequeñas y ejercita
justo lo que ya existe en el runtime (campos `int`, `ifle`, `if_icmpge`, `goto`, `ireturn`,
`putfield`), sin arrastrar tipos externos, estáticos ni interfaces.

## Lo que falta en el compilador (medido, no supuesto)

- `object::compile_object` (usado por `object-demo`) **no sirve**: exige campos `int`,
  métodos `()I` y no traduce ramas (`if*`/`goto` no aparecen en su `lower`). `TickThrottler`
  declara `()V` y `()Z` y tiene dos saltos condicionales.
- `numeric::compile_jar` compila **un** método y genera un `main` con su CLI; `compile_instance`
  solo funciona con `multi_classes` inicializado (multi-static-demo).
- No existe una ruta que compile **todas** las declaraciones de una clase y dé un driver.

## Paso propuesto (A-02 fase 3)

Añadir `mc-aot class-demo <server.jar> <clase> <binario>`:

1. **Admisión**: la clase cae en el perfil (mismas reglas que `numeric_bridge_layout.py`,
   reutilizadas, no reescritas) y no tiene bloqueo de ejecución. Si no, rechazo con el
   **motivo nombrado** del censo (`campos estáticos`, `interfaces: …`, `referencia fuera del
   JAR`, `volatile`, …) y exit 2. Nada de «se intentó».
2. **Traducción**: constructor + todos los métodos declarados, vía `numeric` (mismo runtime y
   mismo `Program`), sin escribir a mano ningún cuerpo.
3. **Driver**: el binario lee un **guion de llamadas** por argv — `new <args>`, `<método>
   <args>`, `read <campo>` — y escribe una línea por paso (`OK` para `void`, el valor para el
   resto; `float`/`double` como bits, igual que el resto de las pruebas).
4. **Diferencial**: `check-vanilla-first-class.py` compara, para cada guion, la salida del
   binario nativo con la del mismo guion ejecutado por un `Driver.java` sobre el **JAR oficial**
   con Java 25, sin Java en `PATH` para el lado nativo.
5. **Controles negativos**: una clase con campo estático, una con interfaz, una con campo
   `float`/`long` (hoy admitida solo si el driver lo soporta) y una con `<clinit>` deben
   rechazarse con motivo nombrado. Que se compile una clase no significa que arranque el
   servidor: `Main` sigue bloqueado y el probe de A-08 no cambia.

## Estado: implementado y en verde (2026-11-07)

`mc-aot class-demo <server.jar> <clase> <binario>` (`numeric::compile_class_demo`) compila el
constructor y **todas** las declaraciones de instancia, y el binario ejecuta un guion por argv:

```
$ bin new 2 5 -- increment -- read count -- increment -- isUnderThreshold \
      -- tick -- tick -- tick -- tick -- tick -- read count
OK
OK
2
OK
1
OK OK OK OK OK
0
```

Es exactamente `TickThrottler(2,5)`: `count` 0 → 2 → 4 (`isUnderThreshold` = 1 porque 4 < 5) y
cinco `tick` lo devuelven a 0.

Prueba: `mc-aot/tests/check-vanilla-first-class.py`, registrada en `run-regressions.sh`.

- **120 guiones aleatorios** (semilla fija) con constructor y 4–12 pasos, salida **idéntica** al
  mismo guion ejecutado por un driver reflectivo sobre el **JAR oficial con Java 25**.
- El binario corre con `PATH=/nonexistent` y sin `JAVA_HOME`: no hay JVM detrás.
- Guardas: paso desconocido, `read` antes de `new` y campo inexistente → exit 2 con motivo.
- Cuatro bloqueos reales del JAR (uno por categoría) se rechazan **diciendo cuál**: `<clinit>`,
  campos estáticos, `interfaces:` y `referencia fuera del JAR` (campo no primitivo).

Comprobado en el censo: `TickThrottler` no tiene bloqueo de layout ni de ejecución, y **no
existe en el JAR ninguna clase con `<clinit>` sin campos estáticos** (3.308 con inicializador,
3.721 con estáticos, 413 estáticos por `ConstantValue` sin `<clinit>`), así que el rechazo por
`<clinit>` se comprueba sobre clases que sí lo declaran.

## Límites declarados (lo que este paso **no** hace)

- Es **una** clase: el contador honesto pasa de `0 / 7.762` a `1 / 7.762`. La mitad (3.881) no
  se mueve ni se declara.
- Solo bases directas de `java/lang/Object`, sin interfaces, sin estáticos, sin `volatile`,
  sin manejadores de excepciones, sin sobrecargas en el driver y con campos primitivos.
- No hay GC, ni publicación compartida, ni `Main`: el probe de A-08 sigue igual.

## Criterio de cierre del paso

`check-vanilla-first-class.py` en la integral: **1 clase completa** (todas sus declaraciones)
traducida y ejecutada, con la misma salida que Java 25 en los guiones generados y rechazos
nombrados. **Cumplido** con 120 guiones (el listón de ≥200 se dejó en 120 por tiempo de la
suite; ampliarlo es cambiar una constante, no el método).

## Corrección (2026-11-07)

Este documento y el registro cerraban con «el contador honesto pasa de 0/7.762 a 1/7.762». Esa frase
**mezclaba dos cosas distintas** y queda corregida:

- `TickThrottler` está **traducida y ejecutada** con 120 guiones diferenciales contra Java 25 (eso es real,
  con `check-vanilla-first-class.py` en la integral).
- El **contador oficial** (`analysis/class-registry.json`) solo se mueve con revisión de otro frente. En ese
  momento el contador seguía en **0/7.762** y `TickThrottler` no estaba registrada como clase rastreada.

El contador oficial pasa a **1/7.762** el mismo día por otro camino legítimo: C tenía `FeatureFlagUniverse`
medida y en `review-required`, A la revisó y la firmó con el predicado en verde (ver
`analysis/a-review-featureflaguniverse.log`); `QuartPos` sigue `review-required` a la espera de B.
`TickThrottler` continúa como **candidata pendiente de revisión externa**: no está registrada y no cuenta.
