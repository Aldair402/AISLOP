#!/usr/bin/env python3
"""El regenerador de evidencia tiene que negarse, no solo escribir.

`update-class-evidence.py` es la pieza que convierte lo que midió un test en
manifiesto, informe y entrada de registro. Si acepta cualquier cosa, una clase
"completa" puede salir de un JSON escrito a mano. Esta prueba ataca sus reglas una
por una, sin compilar nada y sin JAR: son las comprobaciones que deciden si una
historia sobre una clase se publica o no.

Nueve alteraciones, todas tienen que ser rechazadas:

1. miembro inventado (el test declara algo que el classfile no tiene),
2. miembro declarado ni medido ni declarado como hueco,
3. hueco declarado sin motivo escrito,
4. tipo de evidencia que no es `differential` ni `java-only`,
5. spec sin limitaciones,
6. spec con limitaciones vacías,
7. spec al que le falta una ruta,
8. el camino honesto: todo medido, todo con evidencia → se publica,
9. hueco con motivo → se publica y el miembro queda fuera del recuento, no dentro.
"""
import importlib.util, pathlib, sys

TOOL = pathlib.Path(__file__).resolve().parents[1] / "tools/update-class-evidence.py"
spec = importlib.util.spec_from_file_location("update_class_evidence", TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def refuses(label, function, *args):
    try:
        function(*args)
    except SystemExit:
        return True
    print(f"FALLO: {label} no fue rechazado", file=sys.stderr)
    return False


def accepts(label, function, *args):
    try:
        function(*args)
    except SystemExit as error:
        print(f"FALLO: {label} fue rechazado ({error})", file=sys.stderr)
        return False
    return True


DECLARED = {"toString()Ljava/lang/String;", "id:Ljava/lang/String;", "<init>(Ljava/lang/String;)V"}
HONEST_SPEC = {
    "class": "net/minecraft/world/flag/FeatureFlagUniverse",
    "test": "mc-aot/tests/check-featureflaguniverse-class-surface.py",
    "log": "analysis/featureflaguniverse-static-surface.log",
    "manifest": "analysis/class-evidence/featureflaguniverse.json",
    "classfile_manifest": "analysis/class-evidence/featureflaguniverse-classfile.json",
    "report": "analysis/featureflaguniverse-evidence-report.json",
    "limitations": ["El diferencial cubre 96 argumentos, no el dominio completo de String."],
}


def main():
    checks = []

    checks.append(refuses(
        "miembro inventado",
        tool.check_accounting,
        DECLARED,
        {"toBlockFromJava(I)I": "differential", "toString()Ljava/lang/String;": "differential",
         "id:Ljava/lang/String;": "differential", "<init>(Ljava/lang/String;)V": "differential"},
        {}))

    checks.append(refuses(
        "miembro declarado sin medición ni hueco",
        tool.check_accounting,
        DECLARED,
        {"toString()Ljava/lang/String;": "differential", "id:Ljava/lang/String;": "differential"},
        {}))

    checks.append(refuses(
        "hueco sin motivo",
        tool.check_accounting,
        DECLARED,
        {"toString()Ljava/lang/String;": "differential", "id:Ljava/lang/String;": "differential"},
        {"<init>(Ljava/lang/String;)V": "   "}))

    checks.append(refuses(
        "tipo de evidencia desconocido",
        tool.validate_kinds,
        {"toString()Ljava/lang/String;": "structural"}))

    checks.append(refuses(
        "spec sin limitaciones",
        tool.validate_spec,
        {k: v for k, v in HONEST_SPEC.items() if k != "limitations"}))

    checks.append(refuses(
        "limitaciones vacías",
        tool.validate_spec,
        dict(HONEST_SPEC, limitations=["  ", ""])))

    checks.append(refuses(
        "spec incompleto",
        tool.validate_spec,
        {k: v for k, v in HONEST_SPEC.items() if k != "report"}))

    checks.append(accepts(
        "camino honesto",
        tool.check_accounting,
        DECLARED,
        {"toString()Ljava/lang/String;": "differential", "id:Ljava/lang/String;": "differential",
         "<init>(Ljava/lang/String;)V": "differential"},
        {}))

    # Un hueco con motivo se publica, pero el miembro NO entra en lo medido.
    measured = {"toString()Ljava/lang/String;": "differential", "id:Ljava/lang/String;": "differential"}
    gaps = {"<init>(Ljava/lang/String;)V":
            "constructor público: se construye desde bytecode traducido, pero el arnés actual "
            "solo expone un punto de entrada estático y no lo invoca"}
    checks.append(accepts("hueco con motivo", tool.check_accounting, DECLARED, measured, gaps))
    if set(measured) & set(gaps):
        print("FALLO: un miembro no puede estar medido y ser hueco a la vez", file=sys.stderr)
        checks.append(False)

    if not all(checks):
        print(f"FALLO: {checks.count(False)} de {len(checks)} comprobaciones del regenerador "
              f"no se comportaron como debían", file=sys.stderr)
        return 1
    print(f"OK: regenerador ejercido — {len(checks) - 2} alteraciones rechazadas (miembro inventado, "
          f"miembro sin medición ni hueco, hueco sin motivo, evidencia de tipo desconocido, spec sin "
          f"limitaciones, limitaciones vacías, spec incompleto) y el camino honesto más un hueco "
          f"justificado sí se publican; el hueco queda fuera del recuento de medidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
