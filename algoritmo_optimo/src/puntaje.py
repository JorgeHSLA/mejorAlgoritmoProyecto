"""Función objetivo Z(A) y validador de restricciones duras R1-R4.

No hay R5 (cupo): el enunciado no da tamaño de clase, así que una clase
admite a todos los estudiantes que la quieran (supuesto S4).

Este módulo es el EVALUADOR INDEPENDIENTE: todos los algoritmos se juzgan
con estas funciones a partir de la asignación final, nunca con el puntaje
que cada algoritmo calcule internamente (ver docs/01_formalizacion.md §4).

Puntaje de un estudiante =
    suma, por cada clase suya, de su valor individual
        (prioridad + empatía - franjas libres que ocupa)
  + 1 punto fijo si pidió franjas libres
  + 3 puntos por cada amigo en la misma clase
  - penalización por CAMINATA: cada día, sus clases en orden de hora, y se
    suman los minutos entre cada clase y la siguiente; el total semanal se
    multiplica por w_cerc y se divide entre el mayor tiempo del campus.

La caminata NO es aditiva por clase (depende de qué clase va antes y
después ese día); por eso se calcula sobre el horario completo.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Iterable, Mapping

from src.modelo import EMPATIA_MAX, PRIORIDAD_MAX, Asignacion, Clase, Estudiante, Instancia

UMBRAL_PRIORITARIO = 4  # p(s,c) >= 4  => curso prioritario
TOLERANCIA = 1e-9       # para comparar puntajes reales

# Índice inverso de la asignación: id de clase -> ids de estudiantes inscritos.
Inscritos = Mapping[str, frozenset[str]]
# Dónde está un estudiante: pares (franja, edificio), en cualquier orden.
Ocupacion = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Violacion:
    regla: str        # "R1".."R4" o "R0" (clase/estudiante inexistente)
    estudiante: str
    detalle: str


def inscritos_por_clase(asignacion: Asignacion) -> dict[str, frozenset[str]]:
    """Invierte A: para cada clase, el conjunto de estudiantes inscritos."""
    temporal: dict[str, set[str]] = {}
    for est_id, clases in asignacion.items():
        for g in clases:
            temporal.setdefault(g, set()).add(est_id)
    return {g: frozenset(ests) for g, ests in temporal.items()}


# --------------------------------------------------------------------------
# Valores por clase
# --------------------------------------------------------------------------

def valor_individual(inst: Instancia, est: Estudiante, sec: Clase) -> float:
    """Valor de la clase por sí sola: prioridad + empatía - franjas libres que ocupa.

    La cercanía no está aquí: depende de las otras clases del mismo día
    (ver ``penalizacion_caminata``).
    """
    w = inst.pesos
    prioridad = est.prioridad_de(sec.curso) or 0
    termino_prio = w.prio * prioridad / PRIORIDAD_MAX
    termino_emp = w.emp * est.empatia_con(sec.profesor) / EMPATIA_MAX
    termino_libre = 0.0
    if est.franjas_libres:
        ocupadas = (sec.mascara & est.mascara_libre).bit_count()
        termino_libre = w.libre * ocupadas / len(est.franjas_libres)
    return termino_prio + termino_emp - termino_libre


def minutos_caminando(ocupacion: Iterable[tuple[int, int]], franjas_por_dia: int,
                      tiempo: Callable[[int, int], int]) -> int:
    """Minutos que camina el estudiante en la semana entre clases del MISMO día.

    Por cada día se ordenan sus clases por hora y se suma el tiempo de cada
    una a la siguiente (0 si están en el mismo edificio, haya o no un hueco
    entre ellas). No se cuenta el trayecto desde o hacia la casa (I2).
    """
    por_dia: dict[int, list[int]] = {}
    for t, edificio in sorted(ocupacion):
        por_dia.setdefault(t // franjas_por_dia, []).append(edificio)
    return sum(tiempo(a, b) for eds in por_dia.values() for a, b in zip(eds, eds[1:]))


def factor_caminata(inst: Instancia) -> float:
    """Puntos por minuto caminado: w_cerc / mayor tiempo del campus (0 si es un solo edificio)."""
    return inst.pesos.cerc / inst.tmax if inst.tmax else 0.0


def penalizacion_caminata(inst: Instancia, clases: Iterable[Clase]) -> float:
    """Puntos que se pierden por caminar entre las clases de un horario completo."""
    ocupacion = [u for g in clases for u in g.ubicacion]
    return factor_caminata(inst) * minutos_caminando(ocupacion, inst.franjas_por_dia, inst.tiempo)


# --------------------------------------------------------------------------
# Función objetivo
# --------------------------------------------------------------------------

def puntaje_estudiante(inst: Instancia, est: Estudiante, asignacion: Asignacion,
                       inscritos: Inscritos) -> float:
    """Puntaje del estudiante con la fórmula completa (amigos solo en sentido a_in)."""
    w = inst.pesos
    total = w.libre if est.franjas_libres else 0.0
    for g_id in sorted(asignacion.get(est.id, frozenset())):
        sec = inst.clase_por_id[g_id]
        companeros = inscritos.get(g_id, frozenset())
        total += valor_individual(inst, est, sec)
        total += w.amigos * len(est.conjunto_amigos & companeros)
    clases = [inst.clase_por_id[g] for g in asignacion.get(est.id, frozenset())]
    return total - penalizacion_caminata(inst, clases)


def puntaje_total(inst: Instancia, asignacion: Asignacion) -> float:
    """Z(A). Supone ids válidos; usar ``validar`` antes si hay dudas."""
    inscritos = inscritos_por_clase(asignacion)
    return sum((puntaje_estudiante(inst, s, asignacion, inscritos)
                for s in inst.estudiantes), 0.0)


# --------------------------------------------------------------------------
# Validador de restricciones duras
# --------------------------------------------------------------------------

def _violaciones_estudiante(inst: Instancia, est: Estudiante,
                            clases: list[Clase]) -> list[Violacion]:
    v: list[Violacion] = []
    for g in clases:
        if est.prioridad_de(g.curso) is None:
            v.append(Violacion("R1", est.id, f"{g.id}: curso {g.curso} no deseado"))
    for g, h in combinations(clases, 2):
        if g.curso == h.curso:
            v.append(Violacion("R2", est.id, f"{g.id} y {h.id} son del curso {g.curso}"))
        if g.mascara & h.mascara:
            v.append(Violacion("R3", est.id, f"{g.id} y {h.id} comparten franjas"))
    creditos = sum(inst.creditos_de(g.curso) for g in clases)
    if creditos > est.max_creditos:
        v.append(Violacion("R4", est.id, f"{creditos} créditos > límite {est.max_creditos}"))
    return v


def validar(inst: Instancia, asignacion: Asignacion) -> tuple[Violacion, ...]:
    """Todas las violaciones de R1-R4 (tupla vacía <=> A es factible)."""
    violaciones: list[Violacion] = []
    for est_id in sorted(asignacion):
        est = inst.estudiante_por_id.get(est_id)
        if est is None:
            violaciones.append(Violacion("R0", est_id, "estudiante inexistente"))
            continue
        existentes = []
        for g_id in sorted(asignacion[est_id]):
            sec = inst.clase_por_id.get(g_id)
            if sec is None:
                violaciones.append(Violacion("R0", est_id, f"clase inexistente {g_id}"))
            else:
                existentes.append(sec)
        violaciones += _violaciones_estudiante(inst, est, existentes)
    return tuple(violaciones)


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------

def cursos_prioritarios(est: Estudiante) -> frozenset[str]:
    return frozenset(d.curso for d in est.deseos if d.prioridad >= UMBRAL_PRIORITARIO)


def porcentaje_prioritarios(inst: Instancia, asignacion: Asignacion) -> float:
    """% de estudiantes con Prio(s) != {} que obtuvieron TODOS sus prioritarios."""
    con_prioritarios = [s for s in inst.estudiantes if cursos_prioritarios(s)]
    if not con_prioritarios:
        return 100.0
    completos = 0
    for s in con_prioritarios:
        obtenidos = {inst.clase_por_id[g].curso
                     for g in asignacion.get(s.id, frozenset())
                     if g in inst.clase_por_id}
        if cursos_prioritarios(s) <= obtenidos:
            completos += 1
    return 100.0 * completos / len(con_prioritarios)
