"""Genera la matriz de trazabilidad Análisis -> Pruebas leyendo los marcadores @pytest.mark.traza.

Uso:  python scripts/trazabilidad.py            # imprime la matriz en Markdown
      python scripts/trazabilidad.py --escribir # actualiza docs/analisis/trazabilidad-pruebas.md
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PATRON_ID = re.compile(r"(US-\d{2}|CU-\d{2}|ADR-\d{3})")
PATRON_MARCA = re.compile(r"traza\(([^)]*)\)")
PATRON_TEST = re.compile(r"^\s*(?:async )?def (test_\w+)", re.M)


def escanear() -> dict[str, set[str]]:
    """Devuelve {ID: {archivo::prueba}}. Un marcador de módulo (pytestmark) cubre todas sus pruebas."""
    mapa: dict[str, set[str]] = defaultdict(set)
    for archivo in sorted((RAIZ / "tests").rglob("test_*.py")):
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        marcas_modulo: set[str] = set()
        pendientes: set[str] = set()
        for linea in lineas:
            m = PATRON_MARCA.search(linea)
            if m and linea.lstrip().startswith("pytestmark"):
                marcas_modulo |= set(PATRON_ID.findall(m.group(1)))
            elif m and linea.lstrip().startswith("@pytest.mark.traza"):
                pendientes |= set(PATRON_ID.findall(m.group(1)))
            t = PATRON_TEST.match(linea)
            if t:
                for i in pendientes | marcas_modulo:
                    mapa[i].add(f"{archivo.relative_to(RAIZ / 'tests').as_posix()}::{t.group(1)}")
                pendientes = set()
    return mapa


def a_markdown(mapa: dict[str, set[str]]) -> str:
    def clave(i):
        return (i[:2], i)
    filas = ["# Trazabilidad requisito → prueba (generada)", "",
             "Generada por `scripts/trazabilidad.py` a partir de los marcadores `@pytest.mark.traza`.", "",
             "| ID | # pruebas | Ejemplos |", "|---|---|---|"]
    for i in sorted(mapa, key=clave):
        pruebas = sorted(mapa[i])
        filas.append(f"| {i} | {len(pruebas)} | `{pruebas[0]}`{' …' if len(pruebas) > 1 else ''} |")
    return "\n".join(filas) + "\n"


if __name__ == "__main__":
    texto = a_markdown(escanear())
    if "--escribir" in sys.argv:
        (RAIZ / "docs" / "analisis" / "trazabilidad-pruebas.md").write_text(texto, encoding="utf-8")
    else:
        print(texto)
