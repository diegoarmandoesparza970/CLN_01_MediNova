"""Ejecuta los 120 casos y 20 transiciones del paquete CSV y escribe los resultados.

    python -m scripts.ejecutar_csv            # escribe docs/evidencias/csv/*.csv
"""
from __future__ import annotations

from pathlib import Path

from tests.csv_modelo.modelo import escribir_resultados

DESTINO = Path(__file__).resolve().parent.parent / "docs" / "evidencias" / "csv"

if __name__ == "__main__":
    r = escribir_resultados(DESTINO)
    cumple = sum(1 for c in r["casos"] if c["resultado_alumno"] == "CUMPLE")
    print(f"casos: {len(r['casos'])} ({cumple} CUMPLE / {len(r['casos']) - cumple} NO_CUMPLE)")
    print(f"transiciones: {len(r['transiciones'])}")
    print(f"resultados en {DESTINO}")
