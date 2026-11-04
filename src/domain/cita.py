from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .estados import ESTADOS_QUE_BLOQUEAN_FRANJA, Disparador, EstadoCita, MaquinaDeEstadosDeCita
from .value_objects import Autorizacion, CierreDeConsulta, Confirmacion, FranjaHoraria


@dataclass
class Cita:
    """Entidad con ciclo de vida controlado por la State Machine."""

    id: str
    expediente: str
    medico_id: str
    sucursal_id: str
    franja: FranjaHoraria
    especialidad: str = ""
    motivo: str = ""
    canal: str = "recepcion"
    aseguradora_id: str | None = None
    autorizacion: Autorizacion | None = None
    estado: EstadoCita = EstadoCita.AGENDADA
    cita_origen_id: str | None = None
    llegada: datetime | None = None
    confirmacion: Confirmacion | None = None
    cierre: CierreDeConsulta | None = None
    creada_en: datetime | None = None
    reagendada_en: datetime | None = None

    def aplicar(self, disparador: Disparador) -> EstadoCita:
        self.estado = MaquinaDeEstadosDeCita.siguiente(self.estado, disparador)
        return self.estado

    @property
    def bloquea_franja(self) -> bool:
        return self.estado in ESTADOS_QUE_BLOQUEAN_FRANJA
