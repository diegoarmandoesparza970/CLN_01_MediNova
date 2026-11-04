"""Un proyecto sin trazabilidad análisis → código → pruebas está incompleto (PIA)."""
import pytest

from scripts.trazabilidad import escanear

pytestmark = pytest.mark.traza("US-01")


def test_cada_historia_de_usuario_y_caso_de_uso_tiene_al_menos_una_prueba():
    mapa = escanear()
    requeridos = [f"US-{i:02d}" for i in range(1, 25)] + [f"CU-{i:02d}" for i in range(1, 6)]
    faltan = [r for r in requeridos if not mapa.get(r)]
    assert not faltan, f"Sin prueba asociada: {faltan}"


def test_cada_adr_tiene_pruebas_asociadas():
    mapa = escanear()
    faltan = [f"ADR-{i:03d}" for i in range(1, 8) if not mapa.get(f"ADR-{i:03d}")]
    assert not faltan, f"ADR sin prueba: {faltan}"


def test_el_dominio_no_importa_infraestructura_ni_api():
    """Validación de la sección 11 del informe: el dominio evita depender de SQL/ORM/infraestructura."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent / "src"
    prohibidos = ("sqlalchemy", "fastapi", "src.infrastructure", "src.api", "src.application", "pydantic")
    for capa in ("domain",):
        for py in (raiz / capa).rglob("*.py"):
            for linea in py.read_text(encoding="utf-8").splitlines():
                if linea.startswith(("import ", "from ")):
                    assert not any(p in linea for p in prohibidos), f"{py.name}: {linea}"
    for py in (raiz / "application").rglob("*.py"):
        for linea in py.read_text(encoding="utf-8").splitlines():
            if linea.startswith(("import ", "from ")):
                assert "sqlalchemy" not in linea and "src.infrastructure" not in linea and "fastapi" not in linea, \
                    f"{py.name}: {linea}"
