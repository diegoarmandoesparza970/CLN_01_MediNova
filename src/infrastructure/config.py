"""Configuración por variables de entorno (12-Factor App, factor III)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(valor: str | None, defecto: bool) -> bool:
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí"}


def normalizar_url_db(url: str) -> str:
    """Render/Heroku entregan 'postgres://'; SQLAlchemy necesita el driver explícito."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


@dataclass(frozen=True)
class Configuracion:
    database_url: str = "sqlite:///./medinova.db"
    app_env: str = "development"
    zona_horaria: str = "America/Monterrey"
    tolerancia_minutos: int = 15
    duracion_cita_minutos: int = 30
    noshow_umbral: int = 3
    confirmacion_limite_horas: int = 24
    seed_demo: bool = False
    whatsapp_modo: str = "simulado"  # simulado | desactivado
    reloj_simulable: bool = False  # habilita /demo/reloj (solo para demostraciones)

    @staticmethod
    def desde_entorno() -> "Configuracion":
        e = os.environ
        return Configuracion(
            database_url=normalizar_url_db(e.get("DATABASE_URL", Configuracion.database_url)),
            app_env=e.get("APP_ENV", "development"),
            zona_horaria=e.get("ZONA_HORARIA", "America/Monterrey"),
            tolerancia_minutos=int(e.get("TOLERANCIA_MINUTOS", 15)),
            duracion_cita_minutos=int(e.get("DURACION_CITA_MINUTOS", 30)),
            noshow_umbral=int(e.get("NOSHOW_UMBRAL", 3)),
            confirmacion_limite_horas=int(e.get("CONFIRMACION_LIMITE_HORAS", 24)),
            seed_demo=_bool(e.get("SEED_DEMO"), False),
            whatsapp_modo=e.get("WHATSAPP_MODO", "simulado"),
            reloj_simulable=_bool(e.get("RELOJ_SIMULABLE"), False),
        )
