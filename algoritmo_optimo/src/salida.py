"""Salida del problema: el horario de CADA CLASE y qué estudiantes tiene.

El algoritmo decide una asignación A (estudiante -> clases). Este módulo la
presenta como la pide el problema, en dos vistas:

* Por clase: curso, profesor, edificio, sus franjas y la lista de estudiantes.
* Por franja (la rejilla): las clases que la ENTRADA pone a esa hora, cada una
  con sus estudiantes.

Nada de esto se decide aquí: qué clases hay en cada franja lo define la
entrada, sin límite (supuesto S5); el algoritmo solo decide dónde van los
estudiantes. Una clase puede quedar sin estudiantes: su lista sale vacía.
"""
from __future__ import annotations

from typing import Any

from src.modelo import Asignacion, Instancia, etiqueta_franja
from src.puntaje import inscritos_por_clase


def _franja(inst: Instancia, t: int) -> dict[str, Any]:
    """Igual que en la entrada, {"dia", "bloque"}, más la hora legible."""
    dia, bloque = divmod(t, inst.franjas_por_dia)
    return {"dia": dia, "bloque": bloque, "cuando": etiqueta_franja(inst, t)}


def _vista_por_clase(inst: Instancia, inscritos: dict[str, frozenset[str]]) -> list[dict[str, Any]]:
    return [{"clase": g.id, "curso": g.curso, "profesor": g.profesor,
             "edificio": inst.edificio_por_id[g.edificio].nombre,
             "horario": [_franja(inst, t) for t in g.franjas],
             "estudiantes": sorted(inscritos.get(g.id, frozenset()))}
            for g in inst.clases]


def _vista_por_franja(inst: Instancia, inscritos: dict[str, frozenset[str]]) -> list[dict[str, Any]]:
    return [{**_franja(inst, t),
             "clases": [{"clase": g, "estudiantes": sorted(inscritos.get(g, frozenset()))}
                        for g in ids]}
            for t, ids in inst.horario.items()]


def horario_resultado(inst: Instancia, asignacion: Asignacion) -> dict[str, Any]:
    """Las dos vistas de la salida: por clase y por franja."""
    inscritos = inscritos_por_clase(asignacion)
    return {"clases": _vista_por_clase(inst, inscritos),
            "por_franja": _vista_por_franja(inst, inscritos)}


def texto_horario(inst: Instancia, asignacion: Asignacion) -> str:
    """Versión legible para la terminal: franja por franja, clase por clase."""
    inscritos = inscritos_por_clase(asignacion)
    lineas = []
    for t, ids in inst.horario.items():
        lineas.append(etiqueta_franja(inst, t))
        for g in ids:
            clase = inst.clase_por_id[g]
            estudiantes = ", ".join(sorted(inscritos.get(g, frozenset()))) or "(sin estudiantes)"
            lineas.append(f"  {g} ({clase.curso}, {clase.profesor}, "
                          f"{inst.edificio_por_id[clase.edificio].nombre}) -> {estudiantes}")
    return "\n".join(lineas)
