# C-18 — Segunda clase del registro, y la evidencia que ya no la escribe una persona

**Rama:** `trabajo/c-18-second-class` · **Base:** `main` `3e7f984` · **Fecha:** 2026-11-05

Con las preguntas cerradas, lo que quedaba abierto era lo de fondo: el registro tenía **una** clase y se
mantenía con un script que conocía esa clase de memoria. Una clase no es un inventario y un script a medida no
es un procedimiento. Esto es lo que faltaba.

## 1. `FeatureFlagUniverse`: la segunda clase, y por qué esa

No la elegí por pequeña. La elegí porque **ya la usa el proyecto en cinco pruebas** —`check-numeric-object-sharing.py`
entre ellas, que comparte una instancia entre heaps— y en todas se ejercita igual: metida en un campo estático.
Nadie había tocado su vertiente de instancia. Es la clase con menos superficie posible (1 campo, 1 constructor,
1 método) que **sí** tiene estado por instancia, así que es el escalón correcto entre `QuartPos` (todo estático)
y cualquier clase con herencia.

```
public class FeatureFlagUniverse {
  private final String id;
  public FeatureFlagUniverse(String id);   // aload_0; invokespecial Object.<init>; putfield id
  public String toString();                // getfield id; areturn
}
```

## 2. El arnés nuevo mide por miembro, no «la clase»

`mc-aot/tests/check-featureflaguniverse-class-surface.py` hace tres cosas y las tres tienen que pasar:

1. **Superficie** — el classfile leído con el parser propio contra la reflexión de Java 25: flags, superclase,
   interfaces, campos, métodos, constructores y modificadores de cada miembro.
2. **Diferencial por miembro**, 3 operaciones × **96 argumentos** = **288 resultados** contra el binario nativo
   sin JVM. Los 96 argumentos incluyen longitudes 0 a 64, unicode, **pares sustitutos fuera del BMP** (emoji),
   controles (NUL, tabulador, salto de línea), comillas, barra invertida y `null`:
   - `<init>(Ljava/lang/String;)V` — se construye dos veces con el mismo argumento: instancia de la clase
     correcta y **objetos distintos**;
   - `toString()Ljava/lang/String;` — devuelve exactamente el argumento: identidad, igualdad y longitud;
   - `id:Ljava/lang/String;` — cada instancia conserva **su** valor: dos con distinto argumento no son
     intercambiables.
3. **Que el camino nativo exista** — el Rust generado tiene que contener el `object_store` del constructor y el
   `object_load` de `toString`. Un resultado correcto puede venir de un camino equivocado; esto obliga a que el
   camino esté.

Cero desacuerdos con Java 25, incluidos los emoji y el NUL. Y ninguna operación produce un resultado trivial:
si todas las filas salieran a cero, el arnés falla, porque un diferencial de ceros no mide nada.

**El detalle que hace honesta la clasificación:** el efecto del constructor y el del campo se observan a través
del `toString` de la propia clase. No hay accesor y no se inventa uno. Eso está declarado como dependencia
cruzada en el informe; si `toString` tradujera mal, la operación de campo también fallaría, y decirlo es
distinto de esconderlo.

## 3. El regenerador de evidencia ya no sabe nada de la clase

`mc-aot/tools/update-class-evidence.py` reemplaza la idea de «un script por clase». Lee un **spec**
(`analysis/class-specs/*.json`) que solo dice dónde vive cada cosa, corre el test, y entonces:

| Regla | Qué impide |
|---|---|
| el test emite lo que midió (`--emit`) | que la evidencia la escriba quien redacta el informe |
| el classfile es la autoridad de miembros | declarar un miembro que no existe, u olvidar uno |
| todo miembro declarado está medido **o** es un hueco con motivo | que el silencio pase por veredicto |
| `differential`/`java-only` y nada más | inventar una tercera categoría de evidencia |
| el spec declara limitaciones no vacías | publicar «completo» sin decir qué no se probó |
| nunca toca `count_complete` ni una firma existente | que la herramienta certifique |

Y `mc-aot/tests/check-update-class-evidence.py` lo ataca con **siete alteraciones** (miembro inventado, miembro
sin medición ni hueco, hueco sin motivo, evidencia de tipo desconocido, spec sin limitaciones, limitaciones
vacías, spec incompleto) más los dos caminos que **sí** deben publicarse: todo medido, y un hueco justificado
que queda fuera del recuento en vez de dentro.

## 4. Estado del registro después de esto

```
net/minecraft/core/QuartPos                 review-required  (5 diferencial, 1 solo-Java inalcanzable)
net/minecraft/world/flag/FeatureFlagUniverse review-required  (3 diferencial, 0 solo-Java)
count_complete calculado: 0 · registrado: 0
```

Dos clases, **ambas a una firma de contar**. El contador sigue en 0 porque la regla R4 del predicado exige
revisión de otro frente (`review` + `reviewer` + `certified: true`), y esa firma no la pone C. Es exactamente el
estado que quería dejar: el trabajo de medir está hecho y verificable, y el número no se mueve por mi mano.

## 5. Lo que cambió en la infraestructura

- `check-class-registry.py` ahora verifica **los hashes de evidencia de todas las clases**, no solo del primer
  manifiesto escrito a mano; y comprueba que cada manifiesto describe la clase que el registro dice.
- El predicado añade las notas de `reflection-gap` al veredicto, para que un hueco declarado se lea sin abrir el
  informe (el bloqueo no cambia: no medido es no medido).
- Cuatro etapas nuevas en `mc-aot/run-regressions.sh` y en el job `quick` de CI: el arnés de la clase, la
  auditoría de su manifiesto, la frescura de su evidencia y la prueba del regenerador.

## Lo que sigue abierto

- Las dos clases esperan firma de A o B (`Q-AC-10`/`Q-BC-12`). No certifico lo mío.
- El spec todavía es uno por clase; cuando haya decenas habrá que permitir varios en una corrida, pero eso es
  mecánica, no semántica.
- La partición por familias sigue sin conectar al predicado: es un mapa de lotes, no un recuento.
