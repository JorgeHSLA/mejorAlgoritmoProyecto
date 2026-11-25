"""PROGRAMACIÓN DINÁMICA TOP-DOWN (memoización) sobre el problema GLOBAL: óptimo exacto Z*.

Idea
----
Se decide a TODOS los estudiantes de un grupo de amigos a la vez, y el estado
de la PD incluye lo que los ya decididos le importan a los que faltan. Por eso
el resultado es el ÓPTIMO GLOBAL. (Resolver a cada estudiante por turnos, aun
de forma exacta, no lo garantiza: quien decide primero no sabe a dónde irán
sus amigos.)

Paso 1: separar por componentes (src/componentes.py)
----------------------------------------------------
Sin tamaño de clase (S4), dos estudiantes solo se afectan si son amigos.
Entonces max Z = Σ_K max Z_K sobre las componentes K del grafo de amistad, y
la PD se corre en cada componente por separado.

Paso 2: PD dentro de una componente
-----------------------------------
Los estudiantes de K se procesan en un orden fijo s_0, ..., s_{n-1} (en grupos
pequeños, de más a menos opciones; si no, BFS: ver ``_ordenar_grupo``). Para decidir
s_i y los siguientes solo importa
  Φ = la elección de los estudiantes YA decididos que tienen algún amigo
      entre los que faltan (la "frontera").
Nada más del pasado afecta al futuro: esa es la propiedad que exige la PD.

Recurrencia
-----------
    OPT(i, Φ) = max_{O ∈ Opc(s_i)}  ganancia(i, O, Φ) + OPT(i+1, Φ')

    ganancia(i, O, Φ) = Σ_{g∈O} v(s_i, g) + w_libre·[Lib(s_i) ≠ ∅]
                        + w_amigos · Σ_{g∈O} Σ_{j<i amigo} ([s_j∈F(s_i)] + [s_i∈F(s_j)])·[g ∈ A(s_j)]

donde Opc(s_i) son los A(s_i) que cumplen R1-R4 (incluye ∅, así que siempre
hay al menos una opción) y Φ' es la frontera de i+1. Respuesta: OPT(0, ∅).

CASO BASE
---------
    OPT(n, Φ) = 0: ya no quedan estudiantes por decidir.

SUBESTRUCTURA ÓPTIMA
--------------------
Fijada la decisión de s_i, lo que queda es exactamente el problema de asignar
a s_{i+1..n-1} dada la frontera Φ'. Si la parte "resto" de una solución
óptima no fuera óptima para ese estado, se reemplaza por una mejor (cortar y
pegar) sin afectar lo ya ganado, porque la ganancia de los estudiantes
futuros solo depende de Φ'. Contradicción. A diferencia de la PD por
estudiante, aquí el estado SÍ captura el acople entre estudiantes.

SUBPROBLEMAS SUPERPUESTOS
-------------------------
Asignaciones distintas del pasado dejan el mismo estado. Ejemplo: si s_0 ya
no tiene amigos entre los que faltan, sus distintas opciones llevan todas a
la MISMA frontera (sin s_0) y OPT(i, Φ) se resuelve una sola vez.

COMPRESIÓN DEL ESTADO (para que se repita más)
---------------------------------------------
De un estudiante j de la frontera NO se guarda toda su elección A(s_j), sino
solo A(s_j) ∩ R_j, donde R_j son las clases de los cursos que desea algún
amigo de j que todavía falta. Lo demás de A(s_j) nunca vuelve a sumar puntos
(nadie que falte puede coincidir con j allí), así que dos pasados que
difieren solo fuera de R_j valen lo mismo hacia adelante. Ejemplo: si j toma
cálculo y física, y su único amigo pendiente solo desea cálculo, da igual en
qué clase de física quedó j.

PODA POR DOMINANCIA (exacta)
----------------------------
Sea P_i el conjunto de clases que s_i podría compartir con ALGÚN amigo (antes
o después en el orden). Si dos opciones de s_i coinciden en O ∩ P_i, ganan
lo mismo por amistad y dejan el mismo estado futuro; solo difieren en Σ v.
Basta conservar la de mayor Σ v. Un estudiante sin amigos se queda con UNA
opción: su óptimo individual (exactamente lo que haría la PD por estudiante).

COMPLEJIDAD
-----------
Sea o = máx |Opc(s)| y w = máx |frontera| dentro de una componente.
  * Estados: O(n · o^w), con o ya reducido por la dominancia. Exponencial en w, que depende de cómo se conectan
    los amigos (con grupos de 2-5 amigos, w <= 4). Si todos fueran amigos
    de todos, w ~ n y la PD sería tan cara como enumerar todas las combinaciones: no puede
    ser de otra forma, el problema general es NP-difícil (formalización §5.2).
  * Tiempo: O(#estados · o · costo de la ganancia).
  * Memoria: O(#estados) + pila de profundidad = tamaño de la componente.
Se rehúsa (EspacioDemasiadoGrande) si la tabla supera ``limite_estados``.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log10, prod

from src.componentes import componentes_amistad
from src.opciones import EspacioDemasiadoGrande, opciones_locales
from src.modelo import Asignacion, Estudiante, Instancia
from src.puntaje import TOLERANCIA

LIMITE_ESTADOS = 2_000_000
MAX_ESTADOS_POSIBLES = 10**9   # cota previa: por encima ni se intenta
GRUPO_PEQUENO = 8             # hasta este tamaño se reordena por número de opciones
MAX_COMPONENTE = 400           # la recursión tiene profundidad = tamaño de la componente
OpcionLocal = tuple[float, frozenset[str]]   # (Σ v(s,g), ids de clase)
Eleccion = tuple[frozenset[str], ...]   # A(s_0), ..., A(s_{i-1}) ya decididos


@dataclass(frozen=True)
class ResultadoGlobal:
    valor: float           # Z* (calculado por la recurrencia)
    asignacion: Asignacion
    estados: int           # tamaño total de las tablas de memoización (para estudiar)


@dataclass(frozen=True)
class _Datos:
    """Todo lo que la recurrencia de UNA componente necesita, precalculado."""
    ests: tuple[Estudiante, ...]
    opciones: tuple[tuple[OpcionLocal, ...], ...]          # Opc(s_i)
    constante: tuple[float, ...]                       # w_libre·[Lib ≠ ∅]
    previos: tuple[tuple[tuple[int, int], ...], ...]  # (j, peso) amigos j < i
    frontera: tuple[tuple[tuple[int, frozenset[str]], ...], ...]  # (j, R_j) con j < i
    w_amigos: float


def _peso_amistad(a: Estudiante, b: Estudiante) -> int:
    return (b.id in a.conjunto_amigos) + (a.id in b.conjunto_amigos)


def _dominantes(opciones: list[tuple[float, tuple[str, ...]]],
                compartibles: frozenset[str]) -> tuple[OpcionLocal, ...]:
    """Una opción por cada O ∩ P_i: la primera, que es la de mayor Σ v (vienen ordenadas)."""
    vistas: set[tuple[str, ...]] = set()
    resultado = []
    for valor, ids in opciones:
        huella = tuple(g for g in ids if g in compartibles)
        if huella not in vistas:
            vistas.add(huella)
            resultado.append((valor, frozenset(ids)))
    return tuple(resultado)


def _deseadas(inst: Instancia, ests: tuple[Estudiante, ...]) -> list[frozenset[str]]:
    return [frozenset(g.id for d in e.deseos for g in inst.clases_por_curso.get(d.curso, ()))
            for e in ests]


def _ordenar_grupo(inst: Instancia, ests: tuple[Estudiante, ...]
                   ) -> tuple[tuple[Estudiante, ...], tuple[tuple[OpcionLocal, ...], ...]]:
    """Opciones (con dominancia) y ORDEN de los estudiantes de un grupo.

    En grupos pequeños (<= GRUPO_PEQUENO) va primero quien tiene MÁS opciones:
    de los primeros el estado solo guarda su huella en las clases compartidas,
    que suele repetirse mucho. Mediana con semilla 42: 273 mil estados en orden
    BFS contra 108 mil así. En grupos grandes se deja el orden BFS, que mantiene
    corta la frontera. El orden NO cambia el óptimo, solo el trabajo.
    """
    deseadas = _deseadas(inst, ests)
    compartibles = [frozenset().union(*(deseadas[k] for k, f in enumerate(ests)
                                        if _peso_amistad(e, f)))
                    for e in ests]   # P_i no depende del orden
    opciones = [_dominantes(opciones_locales(inst, e), compartibles[i])
                for i, e in enumerate(ests)]
    orden = list(range(len(ests)))
    if len(ests) <= GRUPO_PEQUENO:
        orden.sort(key=lambda i: -len(opciones[i]))   # estable: empates en orden BFS
    return tuple(ests[i] for i in orden), tuple(opciones[i] for i in orden)


def _preparar(inst: Instancia, grupo: tuple[Estudiante, ...]) -> _Datos:
    ests, opciones = _ordenar_grupo(inst, grupo)
    n = len(ests)
    pesos = [[_peso_amistad(ests[a], ests[b]) for b in range(n)] for a in range(n)]
    deseadas = _deseadas(inst, ests)
    previos = tuple(tuple((j, pesos[i][j]) for j in range(i) if pesos[i][j])
                    for i in range(n))
    return _Datos(ests, opciones,
                  tuple(inst.pesos.libre if e.franjas_libres else 0.0 for e in ests),
                  previos, _fronteras(pesos, deseadas), inst.pesos.amigos)


def _fronteras(pesos: list[list[int]], deseadas: list[frozenset[str]]
               ) -> tuple[tuple[tuple[int, frozenset[str]], ...], ...]:
    """frontera[i] = ((j, R_j), ...): j < i con algún amigo k >= i, y R_j = clases
    que esos amigos pendientes podrían compartir con j. O(n · grado²)."""
    n = len(pesos)
    por_i: list[list[tuple[int, frozenset[str]]]] = [[] for _ in range(n + 1)]
    for j in range(n):
        posteriores = [k for k in range(j + 1, n) if pesos[j][k]]
        for pos, k in enumerate(posteriores):
            # Para i en (amigo anterior, k], los amigos pendientes de j son posteriores[pos:].
            relevantes = frozenset().union(*(deseadas[x] for x in posteriores[pos:]))
            inicio = posteriores[pos - 1] + 1 if pos else j + 1
            for i in range(inicio, k + 1):
                por_i[i].append((j, relevantes))
    return tuple(tuple(f) for f in por_i)


def _estados_posibles(datos: _Datos) -> int:
    """Cota de la tabla: Σ_i Π_{(j, R_j) ∈ frontera(i)} #{A ∩ R_j : A ∈ Opc(s_j)}.

    Se mira ANTES de empezar, para rehusarse sin gastar el trabajo.
    """
    return sum(prod(len({ids & rel for _, ids in datos.opciones[j]})
                    for j, rel in f)
               for f in datos.frontera)


class _Memo:
    """Tabla de memoización OPT(i, Φ) -> (valor, índice de la mejor opción)."""

    def __init__(self, datos: _Datos, limite: int) -> None:
        self.d = datos
        self.limite = limite
        self.tabla: dict[tuple, tuple[float, int]] = {}

    def clave(self, i: int, elec: Eleccion) -> tuple:
        """Estado: (i, elección de la frontera proyectada a R_j). Nada más importa."""
        return (i, tuple(elec[j] & rel for j, rel in self.d.frontera[i]))

    def ganancia(self, i: int, opcion: OpcionLocal, elec: Eleccion) -> float:
        valor, ids = opcion
        amistad = sum(peso * len(ids & elec[j]) for j, peso in self.d.previos[i])
        return valor + self.d.constante[i] + self.d.w_amigos * amistad

    def opt(self, i: int, elec: Eleccion) -> float:
        if i == len(self.d.ests):                       # caso base
            return 0.0
        clave = self.clave(i, elec)
        if clave in self.tabla:                         # subproblema ya resuelto
            return self.tabla[clave][0]
        if len(self.tabla) >= self.limite:
            raise EspacioDemasiadoGrande(
                f"demasiado grande: la PD global superó {self.limite} estados")
        mejor, mejor_k = float("-inf"), -1
        puntos = self._puntos_por_clase(i, elec)
        fijo, rel_i = self._clave_siguiente(i, elec)
        for k, (valor, ids) in enumerate(self.d.opciones[i]):
            ganancia = valor + self.d.constante[i] + sum(puntos.get(g, 0.0) for g in ids)
            sig = (i + 1, fijo if rel_i is None else fijo + (ids & rel_i,))
            resto = self.tabla[sig][0] if sig in self.tabla else self.opt(i + 1, elec + (ids,))
            if ganancia + resto > mejor + TOLERANCIA:   # desempate: primera opción
                mejor, mejor_k = ganancia + resto, k
        self.tabla[clave] = (mejor, mejor_k)
        return mejor

    def _puntos_por_clase(self, i: int, elec: Eleccion) -> dict[str, float]:
        """Puntos de amistad que gana s_i en cada clase, según los amigos YA decididos.

        Se calcula una vez por estado; así cada opción solo suma (equivale a
        ``ganancia``, pero sin repetir el trabajo para cada opción).
        """
        puntos: dict[str, float] = {}
        for j, peso in self.d.previos[i]:
            for g in elec[j]:
                puntos[g] = puntos.get(g, 0.0) + self.d.w_amigos * peso
        return puntos

    def _clave_siguiente(self, i: int, elec: Eleccion
                         ) -> tuple[tuple[frozenset[str], ...], frozenset[str] | None]:
        """Parte de la clave de (i+1) que NO depende de la opción de s_i, y R_i si s_i
        queda en la frontera (siempre va de último, porque es el mayor índice)."""
        frontera = self.d.frontera[i + 1]
        if frontera and frontera[-1][0] == i:
            return tuple(elec[j] & rel for j, rel in frontera[:-1]), frontera[-1][1]
        return tuple(elec[j] & rel for j, rel in frontera), None


def _reconstruir(memo: _Memo) -> dict[str, frozenset[str]]:
    """Sigue las decisiones guardadas desde el estado inicial (i=0, Φ=∅)."""
    elec: Eleccion = ()
    asignacion = {}
    for i, est in enumerate(memo.d.ests):
        _, k = memo.tabla[memo.clave(i, elec)]
        ids = memo.d.opciones[i][k][1]
        asignacion[est.id] = ids
        elec = elec + (ids,)
    return asignacion


def _rehusar_si_inviable(todos: list[_Datos]) -> None:
    posibles = sum(_estados_posibles(d) for d in todos)
    if posibles > MAX_ESTADOS_POSIBLES:
        raise EspacioDemasiadoGrande(
            f"demasiado grande: ~10^{log10(posibles):.0f} estados posibles; la frontera "
            "de amigos es muy ancha para la PD global")


def optimo(inst: Instancia, limite_estados: int = LIMITE_ESTADOS) -> ResultadoGlobal:
    """Óptimo GLOBAL exacto por PD top-down. Lanza EspacioDemasiadoGrande si no cabe."""
    componentes = componentes_amistad(inst)
    if max((len(k) for k in componentes), default=0) > MAX_COMPONENTE:   # antes de preparar
        raise EspacioDemasiadoGrande(
            f"demasiado grande: una componente de amistad tiene más de {MAX_COMPONENTE} "
            "estudiantes (profundidad de recursión)")
    todos = [_preparar(inst, k) for k in componentes]
    _rehusar_si_inviable(todos)
    valor, asignacion, estados = 0.0, {}, 0
    for datos in todos:
        memo = _Memo(datos, limite_estados - estados)
        try:
            valor += memo.opt(0, ())
        except RecursionError as exc:   # llamador con la pila ya profunda
            raise EspacioDemasiadoGrande("demasiado grande: la recursión de la PD global "
                                         "superó la pila de Python") from exc
        asignacion |= _reconstruir(memo)
        estados += len(memo.tabla)
    return ResultadoGlobal(valor, asignacion, estados)


def resolver_con_valor(inst: Instancia) -> tuple[float, Asignacion]:
    r = optimo(inst)
    return r.valor, r.asignacion


def resolver(inst: Instancia) -> Asignacion:
    """Lo que usa la CLI con --algoritmo pd-global."""
    return optimo(inst).asignacion
