"""Comprueba que los ejemplos entregados den el puntaje óptimo esperado y sean válidos."""
import unittest
from pathlib import Path

from main import resolver
from src.entrada import cargar_instancia

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplo"


class TestEjemplos(unittest.TestCase):
    def _resolver(self, nombre):
        return resolver(cargar_instancia(EJEMPLOS / nombre))

    def test_t5_da_44_y_cumple_las_reglas(self):
        r = self._resolver("entrada_t5.json")
        self.assertAlmostEqual(r["puntaje"], 44.0)
        self.assertEqual(r["violaciones"], [])
        self.assertEqual(r["asignacion"], {"s1": ["g2", "k"], "s2": ["g2", "h"]})

    def test_pequena_da_88_40(self):
        r = self._resolver("entrada_pequena.json")
        self.assertAlmostEqual(r["puntaje"], 88.40, places=2)
        self.assertEqual(r["violaciones"], [])


if __name__ == "__main__":
    unittest.main()
