from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.application.puertos import Reloj


class RelojDelSistema(Reloj):
    """Hora local de la clínica, sin zona (naive), coherente con las franjas."""

    def __init__(self, zona: str = "America/Monterrey"):
        self.zona = ZoneInfo(zona)

    def ahora(self) -> datetime:
        return datetime.now(self.zona).replace(tzinfo=None, microsecond=0)


class RelojFijo(Reloj):
    """Para pruebas: permite simular 14, 15 o 16 minutos de retraso sin esperar."""

    def __init__(self, ahora: datetime):
        self._ahora = ahora

    def ahora(self) -> datetime:
        return self._ahora

    def fijar(self, ahora: datetime):
        self._ahora = ahora


class RelojSimulable(Reloj):
    """Solo para demostraciones: sigue la hora real hasta que se fija una hora simulada."""

    def __init__(self, base: Reloj):
        self.base = base
        self.simulada: datetime | None = None

    def ahora(self) -> datetime:
        return self.simulada or self.base.ahora()

    def fijar(self, ahora: datetime | None):
        self.simulada = ahora
