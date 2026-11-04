"""Exporta la especificación OpenAPI a docs/api/openapi.json (sin arrancar servidor ni BD)."""
import json
from pathlib import Path

from src.api.main import crear_app
from src.infrastructure.config import Configuracion

RAIZ = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    app = crear_app(Configuracion(database_url="sqlite://"))
    destino = RAIZ / "docs" / "api" / "openapi.json"
    destino.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OpenAPI escrito en {destino}")
