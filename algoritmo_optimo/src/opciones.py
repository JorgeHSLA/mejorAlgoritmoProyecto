"""Opciones de horario de un estudiante: todas sus combinaciones factibles.

Una "opción" de un estudiante es un conjunto de clases que cumple las reglas
R1 a R4 (solo cursos deseados, una clase por curso, sin choques, sin pasar el
límite de créditos). La PD global decide, para cada estudiante, cuál de estas
opciones toma. Cada opción trae su valor: suma de lo que valen sus clases
menos la penalización por caminar del horario completo.
"""
from __future__ import annotations

from itertools import product

from src.modelo import Estudiante, Instancia
from src.puntaje import penalizacion_caminata, valor_individual


class EspacioDemasiadoGrande(ValueError):
    """La búsqueda global exhaustiva no es viable para esta instancia."""


def opciones_locales(inst: Instancia, est: Estudiante) -> list[tuple[float, tuple[str, ...]]]:
    """Todas las A(s) factibles según R1-R4, con sum v - caminata del horario.

    Orden: (valor desc, ids asc) => buenas soluciones primero (mejor poda) y
    recorrido determinista.
    """
    grupos = [inst.clases_por_curso.get(d.curso, ()) for d in est.deseos]
    creditos = [inst.creditos_de(d.curso) for d in est.deseos]
    valores = {g.id: valor_individual(inst, est, g) for gs in grupos for g in gs}
    opciones = []
    for combo in product(*[(None, *gs) for gs in grupos]):
        mascara, total_cr, ok = 0, 0, True
        for cr, g in zip(creditos, combo):
            if g is None:
                continue
            total_cr += cr
            if mascara & g.mascara or total_cr > est.max_creditos:
                ok = False
                break
            mascara |= g.mascara
        if ok:
            elegidas = [g for g in combo if g is not None]
            ids = tuple(sorted(g.id for g in elegidas))
            valor = sum(valores[i] for i in ids) - penalizacion_caminata(inst, elegidas)
            opciones.append((valor, ids))
    opciones.sort(key=lambda o: (-o[0], o[1]))
    return opciones
