"""Algoritmo óptimo de asignación de horarios estudiantiles: PD global (exacta).

Uso:
    python main.py --entrada ejemplo/entrada_t5.json
    python main.py --entrada ejemplo/entrada_t5.json --salida salida.json
    python main.py --entrada ejemplo/entrada_t5.json --texto

Lee una instancia (JSON), calcula la asignación de MAYOR puntaje total posible
con la programación dinámica global (src/pd_global.py), la valida con el
evaluador independiente (src/puntaje.py) y escribe el resultado.

Códigos de salida: 0 = ok, 1 = la asignación viola alguna regla (no debería
pasar), 2 = entrada inválida, instancia demasiado grande o error de archivo.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from src.entrada import cargar_instancia
from src.opciones import EspacioDemasiadoGrande
from src.modelo import Instancia
from src.pd_global import optimo
from src.puntaje import porcentaje_prioritarios, puntaje_total, validar
from src.salida import horario_resultado, texto_horario


def resolver(inst: Instancia) -> dict[str, Any]:
    """Corre la PD global y arma el resultado completo (asignación, puntaje, validación)."""
    inicio = time.perf_counter()
    resultado = optimo(inst)
    tiempo = time.perf_counter() - inicio
    asignacion = {s.id: frozenset(resultado.asignacion.get(s.id, frozenset()))
                  for s in inst.estudiantes}
    violaciones = validar(inst, asignacion)
    return {
        "algoritmo": "pd-global",
        **horario_resultado(inst, asignacion),
        "asignacion": {s: sorted(gs) for s, gs in sorted(asignacion.items())},
        "puntaje": round(puntaje_total(inst, asignacion), 6),
        "violaciones": [{"regla": v.regla, "estudiante": v.estudiante, "detalle": v.detalle}
                        for v in violaciones],
        "metricas": {"tiempo_s": round(tiempo, 6),
                     "estados_en_memoria": resultado.estados,
                     "pct_prioritarios": round(porcentaje_prioritarios(inst, asignacion), 2)},
        "_asignacion": asignacion,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Asignación óptima de horarios (PD global)")
    parser.add_argument("--entrada", required=True, help="ruta del JSON de la instancia")
    parser.add_argument("--salida", help="opcional: guardar el resultado en este archivo")
    parser.add_argument("--texto", action="store_true",
                        help="horario legible (franja, clase, estudiantes) en vez de JSON")
    args = parser.parse_args(argv)
    try:
        inst = cargar_instancia(args.entrada)
        resultado = resolver(inst)
    except (ValueError, EspacioDemasiadoGrande) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error de archivo: {exc}", file=sys.stderr)
        return 2

    asignacion = resultado.pop("_asignacion")
    if args.texto:
        texto = texto_horario(inst, asignacion)
    else:
        texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(texto, encoding="utf-8")
        print(f"Resultado guardado en {args.salida}")
    else:
        print(texto)
    print(f"pd-global: puntaje={resultado['puntaje']:.2f} "
          f"violaciones={len(resultado['violaciones'])} "
          f"tiempo={resultado['metricas']['tiempo_s']:.4f}s", file=sys.stderr)
    return 0 if not resultado["violaciones"] else 1


if __name__ == "__main__":
    sys.exit(main())
