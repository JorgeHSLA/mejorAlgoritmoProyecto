"""Modelo de datos compartido (entradas y salidas) del problema de horarios.

Todas las clases son dataclasses inmutables (frozen=True): ningún algoritmo
puede modificar la instancia por accidente. Los índices de búsqueda (por id)
se calculan una sola vez con ``cached_property``, que escribe directamente en
``__dict__`` y por eso es compatible con ``frozen=True``.

Notación (ver docs/01_formalizacion.md):
    franja t = dia * franjas_por_dia + bloque, y un conjunto de franjas se
    representa como máscara de bits (bit t encendido <=> franja t ocupada).

Una CLASE es fija: su curso, su profesor, su edificio y sus franjas vienen
dados en la entrada (el horario). Lo único que decide el algoritmo es QUÉ
ESTUDIANTES quedan en cada clase. No hay tamaño máximo de clase (supuesto
S4 de la formalización), y si una franja tiene varias clases, cada una se
dicta aparte (supuesto S5). Cuántas clases hay a cada hora lo define la entrada,
sin límite; un estudiante solo puede estar en una de ellas (R3).

La lectura y escritura del JSON está en src/entrada.py.

Todos los datos que maneja este proyecto son SINTÉTICOS.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Mapping

# Asignación A: S -> P(G). id de estudiante -> ids de clases inscritas.
Asignacion = Mapping[str, frozenset[str]]

PRIORIDAD_MIN, PRIORIDAD_MAX = 1, 5
EMPATIA_MIN, EMPATIA_MAX = 0, 5

# Supuesto S2 (nuestro, el enunciado no lo dice): bloques de 2 horas que
# empiezan a las 7:00. Solo se usa para mostrar la salida de forma legible.
NOMBRES_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
HORA_INICIO, HORAS_POR_BLOQUE = 7, 2
MAX_FRANJAS_POR_DIA = (24 - HORA_INICIO) // HORAS_POR_BLOQUE


def mascara_de(franjas: tuple[int, ...] | frozenset[int]) -> int:
    """Convierte un conjunto de franjas en máscara de bits: sum(2**t)."""
    mascara = 0
    for t in franjas:
        mascara |= 1 << t
    return mascara


@dataclass(frozen=True)
class Pesos:
    """Pesos w de la función objetivo (todos >= 0)."""
    prio: float = 10.0
    emp: float = 2.0
    cerc: float = 2.0
    libre: float = 1.0
    amigos: float = 3.0


@dataclass(frozen=True)
class Edificio:
    """Entrada del catálogo de edificios: id entero y nombre."""
    id: int
    nombre: str


@dataclass(frozen=True)
class Curso:
    id: str
    nombre: str
    creditos: int


@dataclass(frozen=True)
class Clase:
    """Una clase g = (curso, profesor, franjas, edificio). Sin cupo (S4).

    ``franjas`` se deduce del horario de la entrada: son las franjas en cuya
    lista aparece la clase.
    """
    id: str
    curso: str
    profesor: str
    franjas: tuple[int, ...]
    edificio: int        # id del edificio (catálogo)

    @cached_property
    def mascara(self) -> int:
        return mascara_de(self.franjas)

    @cached_property
    def ubicacion(self) -> tuple[tuple[int, int], ...]:
        """Pares (franja, edificio): dónde está el estudiante en cada franja de la clase."""
        return tuple((t, self.edificio) for t in self.franjas)


@dataclass(frozen=True)
class Deseo:
    """Curso deseado con prioridad p(s,c) en 1..5 (5 = más necesario)."""
    curso: str
    prioridad: int


@dataclass(frozen=True)
class Estudiante:
    id: str
    max_creditos: int
    deseos: tuple[Deseo, ...]
    # Pares (profesor, empatía 0..5); un profesor ausente vale 0.
    empatia: tuple[tuple[str, int], ...] = ()
    amigos: tuple[str, ...] = ()
    franjas_libres: tuple[int, ...] = ()

    @cached_property
    def _empatia_dict(self) -> dict[str, int]:
        return dict(self.empatia)

    @cached_property
    def _prioridades(self) -> dict[str, int]:
        return {d.curso: d.prioridad for d in self.deseos}

    @cached_property
    def conjunto_amigos(self) -> frozenset[str]:
        return frozenset(self.amigos)

    @cached_property
    def mascara_libre(self) -> int:
        return mascara_de(self.franjas_libres)

    def empatia_con(self, profesor: str) -> int:
        return self._empatia_dict.get(profesor, 0)

    def prioridad_de(self, curso: str) -> int | None:
        """Prioridad del curso si es deseado; None si no lo desea."""
        return self._prioridades.get(curso)

    @property
    def suma_prioridades(self) -> int:
        return sum(d.prioridad for d in self.deseos)


@dataclass(frozen=True)
class Instancia:
    dias: int
    franjas_por_dia: int
    pesos: Pesos
    edificios: tuple[Edificio, ...]
    # tiempos[i][j] = minutos caminando entre edificios[i] y edificios[j]. Vienen
    # DADOS en la entrada (no se calculan); la matriz se arma en src/entrada.py.
    tiempos: tuple[tuple[int, ...], ...]
    cursos: tuple[Curso, ...]
    profesores: tuple[str, ...]
    clases: tuple[Clase, ...]
    estudiantes: tuple[Estudiante, ...]

    @property
    def num_franjas(self) -> int:
        return self.dias * self.franjas_por_dia

    @cached_property
    def horario(self) -> dict[int, tuple[str, ...]]:
        """Franja t -> ids de las clases que se dictan en t (orden por id).

        Es la vista "por franja" de la entrada. Clases de la misma franja son
        clases DISTINTAS (S5); un estudiante solo puede estar en una (R3).
        """
        por_franja: dict[int, list[str]] = {}
        for g in self.clases:
            for t in g.franjas:
                por_franja.setdefault(t, []).append(g.id)
        return {t: tuple(sorted(ids)) for t, ids in sorted(por_franja.items())}

    @cached_property
    def curso_por_id(self) -> dict[str, Curso]:
        return {c.id: c for c in self.cursos}

    @cached_property
    def clase_por_id(self) -> dict[str, Clase]:
        return {g.id: g for g in self.clases}

    @cached_property
    def estudiante_por_id(self) -> dict[str, Estudiante]:
        return {s.id: s for s in self.estudiantes}

    @cached_property
    def clases_por_curso(self) -> dict[str, tuple[Clase, ...]]:
        """G_c, cada tupla ordenada por id de clase (determinismo)."""
        agrupadas: dict[str, list[Clase]] = {c.id: [] for c in self.cursos}
        for g in self.clases:
            agrupadas.setdefault(g.curso, []).append(g)
        return {c: tuple(sorted(gs, key=lambda g: g.id)) for c, gs in agrupadas.items()}

    @cached_property
    def _indice_edificio(self) -> dict[int, int]:
        return {e.id: i for i, e in enumerate(self.edificios)}

    @cached_property
    def edificio_por_id(self) -> dict[int, Edificio]:
        return {e.id: e for e in self.edificios}

    @cached_property
    def tmax(self) -> int:
        """Mayor tiempo entre dos edificios (normaliza la cercanía)."""
        return max((max(fila) for fila in self.tiempos), default=0)

    def tiempo(self, a: int, b: int) -> int:
        """Minutos caminando entre los edificios con ids a y b."""
        idx = self._indice_edificio
        return self.tiempos[idx[a]][idx[b]]

    def creditos_de(self, curso: str) -> int:
        return self.curso_por_id[curso].creditos


# --------------------------------------------------------------------------
# Validación de instancias (frontera del sistema: el JSON no es confiable)
# --------------------------------------------------------------------------

def _errores_tiempos(inst: Instancia) -> list[str]:
    n = len(inst.edificios)
    if len(inst.tiempos) != n or any(len(f) != n for f in inst.tiempos):
        return [f"tiempos debe cubrir los {n} edificios contra todos"]
    errores = []
    for i in range(n):
        if inst.tiempos[i][i] != 0:
            errores.append(f"el tiempo de {inst.edificios[i].nombre} a sí mismo debe ser 0")
        for j in range(n):
            d = inst.tiempos[i][j]
            if d < 0 or d != inst.tiempos[j][i]:
                errores.append(f"tiempo entre {inst.edificios[i].nombre} y "
                               f"{inst.edificios[j].nombre}: debe ser >= 0 e igual en ambos sentidos")
    return errores


def _errores_clases(inst: Instancia) -> list[str]:
    errores = []
    edificios, profesores = set(inst.edificio_por_id), set(inst.profesores)
    for g in inst.clases:
        if g.curso not in inst.curso_por_id:
            errores.append(f"clase {g.id}: curso inexistente {g.curso}")
        if g.profesor not in profesores:
            errores.append(f"clase {g.id}: profesor inexistente {g.profesor}")
        if g.edificio not in edificios:
            errores.append(f"clase {g.id}: edificio inexistente {g.edificio}")
        if not g.franjas:
            errores.append(f"clase {g.id}: no aparece en ninguna franja del horario")
        if len(set(g.franjas)) != len(g.franjas) or any(
                not 0 <= t < inst.num_franjas for t in g.franjas):
            errores.append(f"clase {g.id}: franjas repetidas o fuera de rango")
    return errores


def _errores_profesores(inst: Instancia) -> list[str]:
    """Supuesto S6: un profesor no puede dictar dos clases en la misma franja."""
    errores = []
    for t, ids in inst.horario.items():
        profesores = [inst.clase_por_id[g].profesor for g in ids]
        for prof in sorted({p for p in profesores if profesores.count(p) > 1}):
            errores.append(f"franja {etiqueta_franja(inst, t)}: el profesor {prof} "
                           "dicta dos clases a la vez")
    return errores


def _errores_estudiante(inst: Instancia, s: Estudiante) -> list[str]:
    errores = []
    if s.max_creditos < 0:
        errores.append(f"estudiante {s.id}: max_creditos negativo")
    cursos = [d.curso for d in s.deseos]
    if len(set(cursos)) != len(cursos):
        errores.append(f"estudiante {s.id}: deseos repetidos")
    for d in s.deseos:
        if d.curso not in inst.curso_por_id:
            errores.append(f"estudiante {s.id}: curso deseado inexistente {d.curso}")
        if not PRIORIDAD_MIN <= d.prioridad <= PRIORIDAD_MAX:
            errores.append(f"estudiante {s.id}: prioridad fuera de 1..5")
    for prof, val in s.empatia:
        if prof not in set(inst.profesores) or not EMPATIA_MIN <= val <= EMPATIA_MAX:
            errores.append(f"estudiante {s.id}: empatía inválida con {prof}")
    for f in s.amigos:
        if f == s.id or f not in inst.estudiante_por_id:
            errores.append(f"estudiante {s.id}: amigo inválido {f}")
    if len(set(s.franjas_libres)) != len(s.franjas_libres) or any(
            not 0 <= t < inst.num_franjas for t in s.franjas_libres):
        errores.append(f"estudiante {s.id}: franjas libres repetidas o fuera de rango")
    return errores


def _ids_duplicados(nombre: str, ids: list[str]) -> list[str]:
    return [f"ids de {nombre} duplicados"] if len(set(ids)) != len(ids) else []


def errores_instancia(inst: Instancia) -> list[str]:
    """Lista de problemas de la instancia (vacía si es válida)."""
    p = inst.pesos
    errores = []
    if not 0 < inst.dias <= len(NOMBRES_DIAS):
        errores.append(f"dias debe estar entre 1 y {len(NOMBRES_DIAS)}")
    if not 0 < inst.franjas_por_dia <= MAX_FRANJAS_POR_DIA:
        errores.append(f"franjas_por_dia debe estar entre 1 y {MAX_FRANJAS_POR_DIA}")
    if min(p.prio, p.emp, p.cerc, p.libre, p.amigos) < 0:
        errores.append("los pesos deben ser >= 0")
    errores += _ids_duplicados("edificios", [str(e.id) for e in inst.edificios])
    errores += _ids_duplicados("profesores", list(inst.profesores))
    errores += _ids_duplicados("cursos", [c.id for c in inst.cursos])
    errores += _ids_duplicados("clases", [g.id for g in inst.clases])
    errores += _ids_duplicados("estudiantes", [s.id for s in inst.estudiantes])
    errores += [f"curso {c.id}: créditos deben ser positivos"
                for c in inst.cursos if c.creditos <= 0]
    errores += _errores_tiempos(inst)
    errores_clases = _errores_clases(inst)
    errores += errores_clases
    if not errores_clases:   # el cruce de profesores supone clases bien formadas
        errores += _errores_profesores(inst)
    for s in inst.estudiantes:
        errores += _errores_estudiante(inst, s)
    return errores


def etiqueta_franja(inst: Instancia, t: int) -> str:
    """Franja legible, p. ej. 'sábado 09:00-11:00' (con el supuesto S2)."""
    dia, bloque = divmod(t, inst.franjas_por_dia)
    inicio = HORA_INICIO + HORAS_POR_BLOQUE * bloque
    nombre = NOMBRES_DIAS[dia] if dia < len(NOMBRES_DIAS) else f"día {dia}"
    return f"{nombre} {inicio:02d}:00-{inicio + HORAS_POR_BLOQUE:02d}:00"
