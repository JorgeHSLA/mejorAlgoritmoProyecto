"""Componentes conexas del grafo de amistad (recorrido BFS).

Sin tamaño de clase (supuesto S4), lo ÚNICO que acopla a dos estudiantes en
Z es el término de amigos. Si s y s' están en componentes distintas del grafo
de amistad (aristas en cualquier sentido), la elección de uno no cambia el
puntaje del otro. Entonces

    max Z = Σ_{componentes K} max Z_K

y cada componente se puede resolver POR SEPARADO. Es una descomposición
exacta (no heurística), estilo divide y vencerás sin paso de combinación:
basta sumar. La PD global la usa.

Complejidad: O(n + m) con n estudiantes y m pares de amigos.
"""
from __future__ import annotations

from collections import deque

from src.modelo import Estudiante, Instancia


def vecinos_amistad(inst: Instancia) -> dict[str, frozenset[str]]:
    """Grafo NO dirigido: s ~ f si f ∈ F(s) o s ∈ F(f)."""
    vecinos: dict[str, set[str]] = {s.id: set(s.amigos) for s in inst.estudiantes}
    for s in inst.estudiantes:
        for f in s.amigos:
            vecinos[f].add(s.id)
    return {s: frozenset(v) for s, v in vecinos.items()}


def componentes_amistad(inst: Instancia) -> list[tuple[Estudiante, ...]]:
    """Componentes en orden determinista: raíz de menor id; dentro, orden BFS.

    El orden BFS deja a cada estudiante cerca de sus amigos, lo que mantiene
    pequeña la "frontera" de la PD global.
    """
    por_id = inst.estudiante_por_id
    vecinos = vecinos_amistad(inst)
    vistos: set[str] = set()
    componentes = []
    for raiz in sorted(por_id):
        if raiz in vistos:
            continue
        vistos.add(raiz)
        cola, componente = deque([raiz]), []
        while cola:
            actual = cola.popleft()
            componente.append(por_id[actual])
            for f in sorted(vecinos[actual] - vistos):
                vistos.add(f)
                cola.append(f)
        componentes.append(tuple(componente))
    return componentes
