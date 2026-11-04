from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .value_objects import FranjaHoraria


@dataclass
class Jornada:
    """Bloque de horas que un médico ofrece en una sucursal (se distingue por id)."""

    id: str
    sucursal_id: str
    franja: FranjaHoraria
    cancelada: bool = False
    cancelada_en: datetime | None = None

    def contiene(self, franja: FranjaHoraria) -> bool:
        return not self.cancelada and self.franja.contiene(franja)
