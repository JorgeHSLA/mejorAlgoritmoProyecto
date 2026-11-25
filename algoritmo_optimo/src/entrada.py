"""Lectura y escritura de instancias en JSON (formato de docs/01_formalizacion.md §6).

La entrada describe un horario FIJO más los estudiantes:

    "edificios": catálogo [{"id": 1, "nombre": "..."}]      (id entero)
    "tiempos":   {"1": {"2": 4, "3": 7}, "2": {"3": 3}}     minutos caminando
    "clases":    catálogo [{id, curso, profesor, edificio}] (sin cupo: S4)
    "horario":   [{"dia": d, "bloque": b, "clases": [ids]}] una entrada por franja

Toda franja se escribe igual en todo el JSON, como {"dia": d, "bloque": b}
(lunes = 0, primer bloque = 0): en el horario y en las franjas libres de cada
estudiante. Por dentro se usa el número día * franjas_por_dia + bloque.

"tiempos" se lee "el edificio 1 está a 4 minutos del 2 y a 7 del 3". Los
tiempos se DAN, no se calculan. Si un par aparece en un solo sentido, vale
para ambos; si aparece en los dos, deben coincidir; si falta, es un error.

Cada franja trae su LISTA de clases. Si la lista tiene varias, son clases
distintas (S5), sin límite de cuántas. Las franjas de cada clase se deducen del
horario: son aquellas en cuya lista aparece.

Lectores ESTRICTOS: el JSON no es confiable, así que no se convierte nada en
silencio (4.9 no pasa a 4, true no pasa a 1, "5" no pasa a 5, NaN se rechaza).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from src.modelo import (Clase, Curso, Deseo, Edificio, Estudiante, Instancia, Pesos,
                        errores_instancia)


def _entero(x: Any, campo: str) -> int:
    if type(x) is not int:                     # excluye bool, float y str
        raise ValueError(f"{campo} debe ser un entero, no {x!r}")
    return x


def _texto(x: Any, campo: str) -> str:
    if not isinstance(x, str):
        raise ValueError(f"{campo} debe ser un texto, no {x!r}")
    return x


def _real(x: Any, campo: str) -> float:
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ValueError(f"{campo} debe ser un número finito, no {x!r}")
    return float(x)


def _lista(x: Any, campo: str) -> list[Any]:
    if not isinstance(x, list):
        raise ValueError(f"{campo} debe ser una lista")
    return x


def _objeto(x: Any, campo: str) -> Mapping[str, Any]:
    if not isinstance(x, dict):
        raise ValueError(f"{campo} debe ser un objeto JSON")
    return x


def _franja(x: Any, dias: int, por_dia: int, campo: str) -> int:
    """{"dia": d, "bloque": b} -> número de franja interno d * por_dia + b."""
    x = _objeto(x, campo)
    dia, bloque = _entero(x["dia"], f"{campo}.dia"), _entero(x["bloque"], f"{campo}.bloque")
    if not (0 <= dia < dias and 0 <= bloque < por_dia):
        raise ValueError(f"{campo}: franja (dia={dia}, bloque={bloque}) fuera de rango")
    return dia * por_dia + bloque


def _franja_a_dict(inst: Instancia, t: int) -> dict[str, int]:
    return {"dia": t // inst.franjas_por_dia, "bloque": t % inst.franjas_por_dia}


def _estudiante_desde_dict(d: Any, dias: int, por_dia: int) -> Estudiante:
    d = _objeto(d, "estudiante")
    return Estudiante(
        id=_texto(d["id"], "estudiante.id"),
        max_creditos=_entero(d["max_creditos"], "max_creditos"),
        deseos=tuple(Deseo(_texto(_objeto(x, "deseo")["curso"], "deseo.curso"),
                           _entero(x["prioridad"], "prioridad"))
                     for x in _lista(d["deseos"], "deseos")),
        empatia=tuple(sorted((k, _entero(v, "empatia"))
                             for k, v in _objeto(d.get("empatia", {}), "empatia").items())),
        amigos=tuple(_texto(a, "amigo") for a in _lista(d.get("amigos", []), "amigos")),
        franjas_libres=tuple(_franja(f, dias, por_dia, "franjas_libres")
                             for f in _lista(d.get("franjas_libres", []), "franjas_libres")),
    )


def _curso_desde_dict(c: Any) -> Curso:
    c = _objeto(c, "curso")
    ident = _texto(c["id"], "curso.id")
    return Curso(ident, _texto(c.get("nombre", ident), "curso.nombre"),
                 _entero(c["creditos"], "creditos"))


def _edificios_desde_lista(x: Any) -> tuple[Edificio, ...]:
    return tuple(Edificio(_entero(_objeto(e, "edificio")["id"], "edificio.id"),
                          _texto(e["nombre"], "edificio.nombre"))
                 for e in _lista(x, "edificios"))


def _id_edificio(clave: str, conocidos: Mapping[int, int]) -> int:
    """Clave de objeto JSON (siempre texto) -> id entero de un edificio conocido."""
    if not clave.lstrip("-").isdigit() or int(clave) not in conocidos:
        raise ValueError(f"tiempos: {clave!r} no es el id de un edificio del catálogo")
    return int(clave)


def _matriz_tiempos(x: Any, edificios: tuple[Edificio, ...]) -> tuple[tuple[int, ...], ...]:
    """Objeto {"id": {"id": minutos}} -> matriz simétrica en el orden del catálogo."""
    pos = {e.id: i for i, e in enumerate(edificios)}
    n = len(edificios)
    matriz: list[list[int | None]] = [[0 if i == j else None for j in range(n)] for i in range(n)]
    for desde, destinos in _objeto(x, "tiempos").items():
        a = pos[_id_edificio(desde, pos)]
        for hasta, minutos in _objeto(destinos, f"tiempos[{desde}]").items():
            b = pos[_id_edificio(hasta, pos)]
            valor = _entero(minutos, f"tiempos[{desde}][{hasta}]")
            if matriz[b][a] is not None and matriz[b][a] != valor:
                raise ValueError(f"tiempos: de {desde} a {hasta} hay {valor} min, "
                                 f"pero al revés hay {matriz[b][a]}")
            matriz[a][b] = matriz[b][a] = valor
    faltan = [(edificios[i].id, edificios[j].id) for i in range(n) for j in range(i + 1, n)
              if matriz[i][j] is None]
    if faltan:
        raise ValueError(f"tiempos: falta el tiempo entre los edificios {faltan[0][0]} y {faltan[0][1]}")
    return tuple(tuple(fila) for fila in matriz)   # type: ignore[arg-type]


def _franjas_por_clase(horario: Any, dias: int, por_dia: int) -> dict[str, list[int]]:
    """Recorre el horario (franja -> lista de clases) y lo invierte: clase -> franjas."""
    franjas: dict[str, list[int]] = {}
    vistas: set[int] = set()
    if dias <= 0 or por_dia <= 0:
        raise ValueError("dias y franjas_por_dia deben ser positivos")
    for entrada in _lista(horario, "horario"):
        entrada = _objeto(entrada, "franja del horario")
        t = _franja(entrada, dias, por_dia, "horario")
        dia, bloque = divmod(t, por_dia)
        if t in vistas:
            raise ValueError(f"horario: la franja (dia={dia}, bloque={bloque}) aparece dos veces")
        vistas.add(t)
        ids = [_texto(g, "horario.clases") for g in _lista(entrada["clases"], "horario.clases")]
        if len(set(ids)) != len(ids):
            raise ValueError(f"horario: una clase aparece dos veces en (dia={dia}, bloque={bloque})")
        for ident in ids:
            franjas.setdefault(ident, []).append(t)
    return franjas


def _clases_desde_dict(datos: Mapping[str, Any], dias: int, por_dia: int) -> tuple[Clase, ...]:
    franjas = _franjas_por_clase(datos["horario"], dias, por_dia)
    catalogo = [_objeto(g, "clase") for g in _lista(datos["clases"], "clases")]
    conocidas = {_texto(g.get("id"), "clase.id") for g in catalogo}
    desconocidas = sorted(set(franjas) - conocidas)
    if desconocidas:
        raise ValueError(f"horario: clases que no están en el catálogo: {', '.join(desconocidas)}")
    return tuple(Clase(_texto(g["id"], "clase.id"), _texto(g["curso"], "clase.curso"),
                       _texto(g["profesor"], "clase.profesor"),
                       tuple(sorted(franjas.get(g["id"], ()))),
                       _entero(g["edificio"], "clase.edificio"))
                 for g in catalogo)


def instancia_desde_dict(datos: Mapping[str, Any]) -> Instancia:
    """Construye y VALIDA una instancia. Lanza ValueError si es inválida."""
    try:
        datos = _objeto(datos, "instancia")
        pesos = _objeto(datos.get("pesos", {}), "pesos")
        dias = _entero(datos["dias"], "dias")
        edificios = _edificios_desde_lista(datos["edificios"])
        por_dia = _entero(datos["franjas_por_dia"], "franjas_por_dia")
        inst = Instancia(
            dias=dias,
            franjas_por_dia=por_dia,
            pesos=Pesos(**{k: _real(v, f"pesos.{k}") for k, v in pesos.items()}),
            edificios=edificios,
            tiempos=_matriz_tiempos(datos["tiempos"], edificios),
            cursos=tuple(_curso_desde_dict(c) for c in _lista(datos["cursos"], "cursos")),
            profesores=tuple(_texto(p, "profesor")
                             for p in _lista(datos["profesores"], "profesores")),
            clases=_clases_desde_dict(datos, dias, por_dia),
            estudiantes=tuple(_estudiante_desde_dict(s, dias, por_dia)
                              for s in _lista(datos["estudiantes"], "estudiantes")),
        )
    except KeyError as exc:
        raise ValueError(f"instancia mal formada: falta el campo {exc}") from exc
    except TypeError as exc:   # p. ej. una clave desconocida en "pesos"
        raise ValueError(f"instancia mal formada: {exc}") from exc
    errores = errores_instancia(inst)
    if errores:
        raise ValueError("instancia inválida:\n  - " + "\n  - ".join(errores[:20]))
    return inst


def _horario_a_lista(inst: Instancia) -> list[dict[str, Any]]:
    return [{**_franja_a_dict(inst, t), "clases": list(ids)} for t, ids in inst.horario.items()]


def instancia_a_dict(inst: Instancia) -> dict[str, Any]:
    p = inst.pesos
    return {
        "dias": inst.dias,
        "franjas_por_dia": inst.franjas_por_dia,
        "pesos": {"prio": p.prio, "emp": p.emp, "cerc": p.cerc,
                  "libre": p.libre, "amigos": p.amigos},
        "edificios": [{"id": e.id, "nombre": e.nombre} for e in inst.edificios],
        "tiempos": {str(a.id): {str(b.id): inst.tiempos[i][j]
                                for j, b in enumerate(inst.edificios) if j != i}
                    for i, a in enumerate(inst.edificios)},
        "cursos": [{"id": c.id, "nombre": c.nombre, "creditos": c.creditos}
                   for c in inst.cursos],
        "profesores": list(inst.profesores),
        "clases": [{"id": g.id, "curso": g.curso, "profesor": g.profesor,
                    "edificio": g.edificio} for g in inst.clases],
        "horario": _horario_a_lista(inst),
        "estudiantes": [{"id": s.id,
                         "max_creditos": s.max_creditos,
                         "deseos": [{"curso": d.curso, "prioridad": d.prioridad}
                                    for d in s.deseos],
                         "empatia": dict(s.empatia), "amigos": list(s.amigos),
                         "franjas_libres": [_franja_a_dict(inst, t) for t in s.franjas_libres]}
                        for s in inst.estudiantes],
    }


def cargar_instancia(ruta: str | Path) -> Instancia:
    """Lee un JSON de instancia. Lanza ValueError con mensaje claro si falla."""
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"no se pudo leer {ruta}: {exc.strerror}") from exc
    try:
        datos = json.loads(texto)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{ruta} no es JSON válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta}: se esperaba un objeto JSON")
    return instancia_desde_dict(datos)


def guardar_instancia(inst: Instancia, ruta: str | Path) -> None:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(instancia_a_dict(inst), ensure_ascii=False, indent=1),
                       encoding="utf-8")
