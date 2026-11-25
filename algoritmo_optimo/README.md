# Algoritmo óptimo: asignación de horarios estudiantiles (PD global)

Proyecto 2026-30, Análisis de Algoritmos. Python 3.12, sin dependencias externas. Los datos de ejemplo son sintéticos.

Esta carpeta contiene solo el algoritmo exacto del proyecto: la **programación dinámica global**, que devuelve la asignación de mayor puntaje total posible.

## Cómo ejecutarlo

```bash
python main.py --entrada ejemplo/entrada_t5.json                       # JSON por pantalla
python main.py --entrada ejemplo/entrada_t5.json --salida salida.json  # guardar el JSON
python main.py --entrada ejemplo/entrada_t5.json --texto               # horario legible
python -m unittest discover -s tests -t .                              # pruebas de los ejemplos
```

## Qué hace

1. Lee la instancia (JSON) y la valida. Una entrada inválida se rechaza con un mensaje.
2. Separa a los estudiantes en **grupos de amigos** (sin tamaño de clase, dos estudiantes solo se afectan si son amigos).
3. Resuelve cada grupo con PD memoizada. La clave de la memoria es `(estudiante i, huella de la frontera de amigos)`.
4. Valida la asignación con un evaluador independiente (reglas R1 a R4) y recalcula el puntaje con la fórmula completa.

Si un grupo de amigos es demasiado grande y enredado, el programa se rehúsa con un mensaje (límite de 2.000.000 estados) en vez de quedarse calculando. El problema general es NP-difícil.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `main.py` | Línea de comandos |
| `src/pd_global.py` | La PD global (el algoritmo) |
| `src/componentes.py` | Grupos de amigos (BFS) |
| `src/opciones.py` | Todas las combinaciones factibles de un estudiante (R1 a R4) y el error de "demasiado grande" |
| `src/puntaje.py` | Función objetivo y validador de reglas |
| `src/modelo.py`, `src/entrada.py`, `src/salida.py` | Modelo de datos, lectura del JSON y salida por clase y por franja |
| `ejemplo/` | Entradas y salidas de ejemplo |

## Ejemplo: `ejemplo/entrada_t5.json`

Dos amigas, s1 y s2. Todas las clases están en un solo edificio.

| Clase | Curso | Profesor | Cuándo |
|---|---|---|---|
| g1 | c | P1 | lunes y miércoles 7 a 9 |
| g2 | c | P2 | lunes y miércoles 9 a 11 |
| h | d | P2 | lunes y miércoles 7 a 9 (a la misma hora que g1) |
| k | e | P2 | lunes y miércoles 13 a 15 |

- s1 desea los cursos c y e (prioridad 5 y 5) y tiene empatía 5 con P1.
- s2 desea los cursos c (5) y d (4).
- Si dos amigas coinciden en una clase, cada una gana 3 puntos.

**Salida** (`ejemplo/salida_t5.json` y `ejemplo/salida_t5.txt`): s1 toma g2 y k, s2 toma g2 y h, con **44 puntos**. s1 renuncia a g1 (su favorita por la empatía con P1) para coincidir con su amiga en g2.

Una estrategia que resuelve a cada estudiante por separado, de forma óptima y en orden, daría 40: s1 tomaría g1 y k (22) y s2 quedaría con g2 y h (18), separadas. La PD global encuentra los 44.

`ejemplo/entrada_pequena.json` es una instancia sintética de 5 estudiantes y 8 clases. Su salida, `ejemplo/salida_pequena.json`, tiene 88.40 puntos.

## Formato de la entrada (resumen)

```json
{
  "dias": 5, "franjas_por_dia": 6,
  "pesos": {"prio": 10, "emp": 2, "cerc": 2, "libre": 1, "amigos": 3},
  "edificios": [{"id": 1, "nombre": "A"}],
  "tiempos": {"1": {}},
  "cursos": [{"id": "c", "nombre": "c", "creditos": 3}],
  "profesores": ["P1"],
  "clases": [{"id": "g1", "curso": "c", "profesor": "P1", "edificio": 1}],
  "horario": [{"dia": 0, "bloque": 0, "clases": ["g1"]}],
  "estudiantes": [{"id": "s1", "max_creditos": 6,
                   "deseos": [{"curso": "c", "prioridad": 5}],
                   "empatia": {"P1": 5}, "amigos": [],
                   "franjas_libres": [{"dia": 0, "bloque": 4}]}]
}
```

`tiempos` son los minutos caminando entre edificios (se piden todos los pares, en un solo sentido basta). Con un solo edificio va vacío.

## Formato de la salida (resumen)

- `clases`: cada clase con su horario fijo y la lista de sus estudiantes.
- `por_franja`: cada franja con sus clases y los estudiantes de cada una.
- `asignacion`: lo mismo visto desde cada estudiante.
- `puntaje`: total recalculado por el evaluador independiente.
- `violaciones`: lista vacía si se cumplen R1 a R4.
- `metricas`: tiempo, estados guardados en la memoria de la PD y porcentaje de estudiantes con todos sus cursos prioritarios.

## Reglas obligatorias

- **R1** solo cursos deseados, **R2** como máximo una clase por curso, **R3** sin choques de horario, **R4** sin pasar del límite de créditos.
- Asignar no es obligatorio: un estudiante puede quedar sin algún curso.
- No hay tamaño máximo de clase.
