# Siguiente bloqueo: identidad para detección de ciclos Log4j

Probe oficial: `analysis/real-eula-primitive-array-class-attempt.log` se detiene al compilar `new IdentityHashMap` en `ParameterFormatter.createDejaVu`; no llega a ejecutar Eula. `javap` de Log4j 2.26.0 muestra `new IdentityHashMap()`, `Collections.newSetFromMap(map)` y una clonación con `Set.addAll`. `appendArray`, `appendMap` y `appendCollection` usan `Set.add` para detectar recursión. Esto es un diagnóstico, no evidencia de un logger funcionando.

Plan de perfil verificable:

1. Representar `IdentityHashMap` con entradas de referencias comparadas por identidad (incluido null), sin sustituirlo por HashMap de igualdad. Mantener mapa y vista como objetos distintos y respaldar la vista por el mismo mapa; `newSetFromMap` exige mapa vacío y conserva los efectos de mutaciones posteriores del mapa. Limitar explícitamente operaciones no implementadas.
2. Modelar `Set.add`, `contains`, `remove`, `clear`, `size` y el `addAll` preciso que se necesite; no inventar orden de iteración, fail-fast ni propiedades de GC. `IdentityHashMap` tiene claves fuertes y admite claves/valores null. No afirmar concurrencia ni igualdad general de conjuntos.
3. Diferenciales Java 25 de identidad (cadenas con mismo valor pero distintas referencias, clases, objetos propios, null, duplicados), vistas vivas, mapa no vacío rechazado, alias y límites/guardas de iteración. Usar bytecode del Log4j oficial y hash para rutas reales cuando sea posible.
4. Repetir probe Eula y registrar siguiente bloqueo; tener presente que el inicializador de `ParameterFormatter` todavía aborta por formatter/zona/locale. No simular logger ni concluir que el servidor arrancó.
5. Mantener aparte la tarea principal: conectar el backend de bytecode al scheduler Rayon con heap compartido, excepciones, inicialización de clases, despacho, terminación y modelo de memoria verificados; el prototipo aún no sustituye `ForkJoinPool` en Main.
