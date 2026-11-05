#!/usr/bin/env python3
"""The two backends must accept at least one common MC_AOT_FUTURES value.

WHY THIS EXISTS
Q-AB-2 asked B to confirm the unified name A implemented, `MC_AOT_FUTURES=completed-only`.
B implemented `MC_AOT_FUTURES=restricted` instead and rejects every other value.
A's backend rejects `restricted`; B's backend rejects `completed-only`. The intersection
is empty: an operator who sets the "unified" variable gets a build failure from one of
the two backends no matter which spelling they pick, and which one fails depends on the
route the program takes. That is worse than no unification, because the error only shows
up on the path that reaches the other backend.

This check reads both opt-in functions from source and compares the accepted literals. It
is static on purpose: parsing two small functions is cheap enough to run on every push,
and it fails with the exact divergence instead of a stack trace.

EXIT CODES
0  both backends accept a common value and the same legacy alias story
1  divergence: nothing in common
2  the source did not match the shape this parser expects (fix the parser, do not skip)
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
A_BACKEND = ROOT / "src/numeric.rs"
B_BACKEND = ROOT / "src/concurrent_compile.rs"

A_FN = re.compile(r"fn futures_optin\(\).*?\n\}", re.S)
B_FN = re.compile(r"fn futures_\w*optin\(\).*?\n\}", re.S)


def accepted(fn_text, name):
    """Literals the function compares the MC_AOT_FUTURES value against.

    Only comparisons of the bound variable (`value == ...`, `v == ...`) count. That
    deliberately excludes `Ok(true)`/`Ok(false)` returns and the `"1"` literal the
    legacy alias uses, which are not values of MC_AOT_FUTURES.
    """
    values = set()
    for match in re.finditer(r'\b(?:value|v)\s*==\s*(?:std::ffi::OsStr::new\()?"([^"]+)"', fn_text):
        values.add(match.group(1))
    if not values:
        print(f"ERROR: no pude extraer valores de {name}; el parser necesita atención", file=sys.stderr)
        raise SystemExit(2)
    return values


def legacy(fn_text):
    return ("MC_AOT_NUMERIC_COMPLETED_FUTURE" in fn_text, "MC_AOT_RAYON_COMPLETED_FUTURE" in fn_text)


def main():
    for path in (A_BACKEND, B_BACKEND):
        if not path.is_file():
            print(f"ERROR: falta {path.relative_to(ROOT.parent)}", file=sys.stderr)
            return 2

    a_text = A_FN.search(A_BACKEND.read_text())
    if not a_text:
        print("ERROR: no encontré `futures_optin` en numeric.rs; ¿cambió de nombre?", file=sys.stderr)
        return 2

    b_file = B_BACKEND.read_text() if B_BACKEND.is_file() else ""
    b_text = B_FN.search(b_file)
    if not b_text:
        # Todavía no hay opt-in propio en el backend concurrente: no se puede comparar
        # nada, y fingir un verde sería peor que decir que falta. El día que la función
        # aparezca, esta etapa pasa a comparar de verdad.
        print("PENDIENTE: el backend concurrente aún no tiene un opt-in de futuros propio;")
        print("  nada que comparar. Cuando `futures_restricted_optin` (o su reemplazo) exista,")
        print("  esta etapa exige que los dos backends compartan al menos un valor MC_AOT_FUTURES.")
        return 0

    a_values = accepted(a_text.group(0), "futures_optin (A)")
    b_values = accepted(b_text.group(0), "futures_restricted_optin (B)")
    common = a_values & b_values

    print(f"A acepta: {sorted(a_values) or 'solo el alias antiguo'}")
    print(f"B acepta: {sorted(b_values) or 'solo el alias antiguo'}")
    print(f"alias heredados A={legacy(a_text.group(0))} B={legacy(b_text.group(0))}")

    if not common:
        print("\nFALLO: los dos backends no comparten ningún valor de MC_AOT_FUTURES.", file=sys.stderr)
        print("  Consecuencia: ningún ajuste del nombre unificado enciende los dos backends.", file=sys.stderr)
        print("  A rechaza todo lo que no sea " + ", ".join(sorted(a_values)), file=sys.stderr)
        print("  B rechaza todo lo que no sea " + ", ".join(sorted(b_values)), file=sys.stderr)
        print("  Arreglo propuesto: un valor canónico aceptado por los dos (propongo `restricted`,", file=sys.stderr)
        print("  porque describe el perfil y no caduca si el perfil crece) y los dos nombres actuales", file=sys.stderr)
        print("  como alias por una versión. C no toca ninguno de los dos backends.", file=sys.stderr)
        return 1

    if len(common) > 1:
        print(f"AVISO: hay más de un valor común ({sorted(common)}); el canónico debería ser uno solo.")
    print(f"OK: los dos backends aceptan {sorted(common)}; el opt-in unificado existe de verdad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
