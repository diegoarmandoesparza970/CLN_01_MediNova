from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CitaAgendadaDto:
    cita_id: str
    estatus: str
    autorizacion: str | None
    advertencias: list[str] = field(default_factory=list)


@dataclass
class ResultadoDeLlegadaDto:
    cita_id: str
    resultado: str
    estatus: str
    mensaje: str
    hora_llegada: datetime | None


@dataclass
class CitaAfectadaDto:
    cita_id: str
    expediente: str
    hora_original: datetime
    estatus: str


@dataclass
class CitaReagendadaDto:
    cita_origen_id: str
    cita_nueva_id: str
    estatus: str


@dataclass
class CambioDeEstatusDto:
    cita_id: str
    estatus: str
    advertencias: list[str] = field(default_factory=list)
