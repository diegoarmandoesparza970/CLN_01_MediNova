"""Commands: intención de cambiar el estado (CQRS, informe sección 6)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from src.domain.value_objects import CierreDeConsulta, FranjaHoraria


@dataclass(frozen=True)
class AgendarCitaCommand:
    medico_id: str
    franja: FranjaHoraria
    sucursal_id: str
    expediente: str
    especialidad: str = ""
    motivo: str = ""
    canal: str = "recepcion"
    aseguradora_id: str | None = None
    numero_autorizacion: str | None = None
    usuario: str = "recepcion"


@dataclass(frozen=True)
class CancelarCitaCommand:
    cita_id: str
    usuario: str
    motivo: str


@dataclass(frozen=True)
class ModificarCitaCommand:
    cita_id: str
    franja: FranjaHoraria
    sucursal_id: str
    usuario: str
    motivo: str


@dataclass(frozen=True)
class RegistrarAutorizacionCommand:
    cita_id: str
    numero: str
    usuario: str


@dataclass(frozen=True)
class PagarComoParticularCommand:
    cita_id: str
    usuario: str


@dataclass(frozen=True)
class RegistrarLlegadaCommand:
    cita_id: str
    usuario: str = "recepcion"
    hora_llegada: datetime | None = None
    telefono: str | None = None  # US-22: validar datos en cada visita
    aseguradora_id: str | None = None
    actualiza_aseguradora: bool = False


@dataclass(frozen=True)
class MarcarNoAtendidaPorRetrasoCommand:
    cita_id: str
    usuario: str = "recepcion"


@dataclass(frozen=True)
class MarcarNoShowCommand:
    cita_id: str
    usuario: str = "recepcion"


@dataclass(frozen=True)
class CerrarConsultaCommand:
    cita_id: str
    cierre: CierreDeConsulta
    usuario: str = "recepcion"
    nueva_cita: AgendarCitaCommand | None = None


@dataclass(frozen=True)
class AbrirJornadaCommand:
    medico_id: str
    sucursal_id: str
    franja: FranjaHoraria


@dataclass(frozen=True)
class CancelarJornadaCommand:
    medico_id: str
    fecha: date
    usuario: str
    motivo: str
    sucursal_id: str | None = None


@dataclass(frozen=True)
class ReagendarCitaCommand:
    cita_id: str
    medico_id: str
    franja: FranjaHoraria
    sucursal_id: str
    usuario: str


@dataclass(frozen=True)
class RegistrarPacienteCommand:
    nombre: str
    telefono: str
    nacimiento: date | None = None
    correo: str = ""
    aseguradora_id: str | None = None


@dataclass(frozen=True)
class ActualizarPacienteCommand:
    expediente: str
    telefono: str | None = None
    correo: str | None = None
    aseguradora_id: str | None = None
    actualiza_aseguradora: bool = False


@dataclass(frozen=True)
class RegistrarRespuestaDeConfirmacionCommand:
    cita_id: str
    respuesta: str
    usuario: str = "recepcion"


@dataclass(frozen=True)
class EnviarConfirmacionesCommand:
    fecha: date  # fecha de las citas a confirmar (normalmente mañana)
    usuario: str = "sistema"
