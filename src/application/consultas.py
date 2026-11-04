"""Queries y View Models (CQRS básico, ADR-004). Los lectores no usan el dominio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ------------------------------------------------------------------ queries
@dataclass(frozen=True)
class ConsultarDisponibilidadDelMedico:
    fecha: date
    medico_id: str | None = None
    especialidad: str | None = None
    sucursal_id: str | None = None
    solo_libres: bool = False


@dataclass(frozen=True)
class ConsultarCitasAfectadas:
    medico_id: str
    fecha: date
    sucursal_id: str | None = None


@dataclass(frozen=True)
class ConsultarHistorialDeNoShows:
    expediente: str


@dataclass(frozen=True)
class ObtenerReporteConsolidado:
    desde: date
    hasta: date


@dataclass(frozen=True)
class ConsultarCitas:
    fecha: date | None = None
    medico_id: str | None = None
    expediente: str | None = None
    estado: str | None = None


# -------------------------------------------------------------- view models
@dataclass
class FranjaVM:
    inicio: datetime
    fin: datetime
    estado: str  # libre | ocupada | sobrecupo_disponible


@dataclass
class DisponibilidadSucursalVM:
    sucursal_id: str
    franjas: list[FranjaVM] = field(default_factory=list)


@dataclass
class DisponibilidadDelMedicoVM:
    medico_id: str
    medico: str
    especialidades: list[str]
    fecha: date
    sucursales: list[DisponibilidadSucursalVM] = field(default_factory=list)


@dataclass
class CitaAfectadaVM:
    cita_id: str
    expediente: str
    paciente: str
    telefono: str
    correo: str
    hora_original: datetime
    estado_reagendado: str  # pendiente | reagendada | cancelada
    nueva_cita_id: str | None = None


@dataclass
class HistorialNoShowsVM:
    expediente: str
    paciente: str
    total: int
    fechas: list[datetime]
    alerta: str | None = None


@dataclass
class FilaReporteVM:
    sucursal_id: str
    medico_id: str
    medico: str
    agendadas: int
    atendidas: int
    no_shows: int
    canceladas: int
    ocupacion_pct: float


@dataclass
class ReporteConsolidadoVM:
    desde: date
    hasta: date
    filas: list[FilaReporteVM]
    total_citas: int
    total_no_shows: int
    tasa_no_show_pct: float
    tiempo_promedio_reagendado_min: float | None  # US-24


@dataclass
class CitaVM:
    id: str
    expediente: str
    paciente: str
    medico_id: str
    sucursal_id: str
    inicio: datetime
    fin: datetime
    estado: str
    canal: str
    especialidad: str
    motivo: str
    aseguradora_id: str | None
    autorizacion: str | None
    numero_autorizacion: str | None
    confirmacion: str | None
    cita_origen_id: str | None
    llegada: datetime | None


@dataclass
class RegistroAuditoriaVM:
    cita_id: str
    tipo: str
    usuario: str
    fecha: datetime
    motivo: str


@dataclass
class NotificacionVM:
    id: int
    cita_id: str | None
    expediente: str
    canal: str
    estado: str
    texto: str
    creada_en: datetime
