"""Esquemas Pydantic de entrada y salida (contrato OpenAPI)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.value_objects import CanalDeSolicitud, FranjaHoraria


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FranjaIn(BaseModel):
    inicio: datetime = Field(examples=["2026-11-10T09:00:00"])
    fin: datetime = Field(examples=["2026-11-10T09:30:00"])

    def a_dominio(self) -> FranjaHoraria:
        return FranjaHoraria(self.inicio, self.fin)


# ----------------------------------------------------------- catálogos
class SucursalIn(BaseModel):
    id: str = Field(min_length=1, max_length=40, examples=["CENTRO"])
    nombre: str


class EspecialidadIn(BaseModel):
    id: str = Field(min_length=1, max_length=40, examples=["CARD"])
    nombre: str


class AseguradoraIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    nombre: str
    exige_autorizacion: bool = False
    anticipacion_horas: int = Field(0, ge=0, description="Horas de anticipación que pide la aseguradora")


class MedicoIn(BaseModel):
    id: str = Field(min_length=1, max_length=40, examples=["MED-010"])
    nombre: str
    especialidades: list[str] = []
    limite_sobrecupo: int = Field(0, ge=0)
    por_honorarios: bool = False


class SobrecupoIn(BaseModel):
    limite: int = Field(ge=0, description="Citas adicionales que el médico acepta (0 = ninguna)")


class SucursalOut(Salida):
    id: str
    nombre: str


class EspecialidadOut(Salida):
    id: str
    nombre: str


class AseguradoraOut(Salida):
    id: str
    nombre: str
    exige_autorizacion: bool
    anticipacion_horas: int


class MedicoOut(BaseModel):
    id: str
    nombre: str
    especialidades: list[str]
    limite_sobrecupo: int
    por_honorarios: bool


# ------------------------------------------------------------ pacientes
class PacienteIn(BaseModel):
    nombre: str = Field(min_length=1)
    telefono: str = Field(examples=["8112345678"])
    nacimiento: date | None = None
    correo: str = ""
    aseguradora_id: str | None = None


class PacienteActualizarIn(BaseModel):
    telefono: str | None = None
    correo: str | None = None
    aseguradora_id: str | None = None
    actualiza_aseguradora: bool = Field(False, description="True para fijar la aseguradora (incluso a null = particular)")


class PacienteOut(BaseModel):
    expediente: str
    nombre: str
    telefono: str
    correo: str
    nacimiento: date | None
    aseguradora_id: str | None


# ---------------------------------------------------------------- citas
class AgendarCitaIn(BaseModel):
    medico_id: str
    sucursal_id: str
    expediente: str
    franja: FranjaIn
    especialidad: str = ""
    motivo: str = ""
    canal: CanalDeSolicitud = CanalDeSolicitud.RECEPCION
    aseguradora_id: str | None = None
    numero_autorizacion: str | None = None


class CitaAgendadaOut(Salida):
    cita_id: str
    estatus: str
    autorizacion: str | None
    advertencias: list[str]


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=1, examples=["El paciente no puede asistir"])


class ModificarIn(BaseModel):
    franja: FranjaIn
    sucursal_id: str
    motivo: str = Field(min_length=1)


class AutorizacionIn(BaseModel):
    numero: str = Field(min_length=1)


class LlegadaIn(BaseModel):
    hora_llegada: datetime | None = Field(None, description="Si se omite se usa el reloj del servidor")
    telefono: str | None = Field(None, description="US-22: teléfono confirmado en recepción")
    aseguradora_id: str | None = None
    actualiza_aseguradora: bool = False


class CierreIn(BaseModel):
    receta: str = ""
    estudios: list[str] = []
    requiere_nueva_cita: bool = False
    nueva_cita: AgendarCitaIn | None = None

    @model_validator(mode="after")
    def _coherencia(self):
        if self.nueva_cita is not None:
            self.requiere_nueva_cita = True
        return self


class ConfirmacionIn(BaseModel):
    respuesta: str = Field(examples=["confirmada"], description="confirmada | rechazada | sin_respuesta")


class EnviarConfirmacionesIn(BaseModel):
    fecha: date


class ReagendarIn(BaseModel):
    medico_id: str
    sucursal_id: str
    franja: FranjaIn


class CambioDeEstatusOut(Salida):
    cita_id: str
    estatus: str
    advertencias: list[str] = []


class ResultadoDeLlegadaOut(Salida):
    cita_id: str
    resultado: str
    estatus: str
    mensaje: str
    hora_llegada: datetime | None


class CitaReagendadaOut(Salida):
    cita_origen_id: str
    cita_nueva_id: str
    estatus: str


class CitaOut(Salida):
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


# -------------------------------------------------------------- jornadas
class JornadaIn(BaseModel):
    medico_id: str
    sucursal_id: str
    franja: FranjaIn


class JornadaOut(BaseModel):
    jornada_id: str


class CancelarJornadaIn(BaseModel):
    medico_id: str
    fecha: date
    sucursal_id: str | None = Field(None, description="Si se omite se cancelan las jornadas de todas las sucursales")
    motivo: str = Field(min_length=1, examples=["Enfermedad del médico"])


class CitaAfectadaOut(Salida):
    cita_id: str
    expediente: str
    hora_original: datetime
    estatus: str


# ------------------------------------------------------------- consultas
class FranjaVMOut(Salida):
    inicio: datetime
    fin: datetime
    estado: str


class DisponibilidadSucursalOut(Salida):
    sucursal_id: str
    franjas: list[FranjaVMOut]


class DisponibilidadOut(Salida):
    medico_id: str
    medico: str
    especialidades: list[str]
    fecha: date
    sucursales: list[DisponibilidadSucursalOut]


class CitaAfectadaVMOut(Salida):
    cita_id: str
    expediente: str
    paciente: str
    telefono: str
    correo: str
    hora_original: datetime
    estado_reagendado: str
    nueva_cita_id: str | None


class HistorialNoShowsOut(Salida):
    expediente: str
    paciente: str
    total: int
    fechas: list[datetime]
    alerta: str | None


class FilaReporteOut(Salida):
    sucursal_id: str
    medico_id: str
    medico: str
    agendadas: int
    atendidas: int
    no_shows: int
    canceladas: int
    ocupacion_pct: float


class ReporteOut(Salida):
    desde: date
    hasta: date
    filas: list[FilaReporteOut]
    total_citas: int
    total_no_shows: int
    tasa_no_show_pct: float
    tiempo_promedio_reagendado_min: float | None


class AuditoriaOut(Salida):
    cita_id: str
    tipo: str
    usuario: str
    fecha: datetime
    motivo: str


class NotificacionOut(Salida):
    id: int
    cita_id: str | None
    expediente: str
    canal: str
    estado: str
    texto: str
    creada_en: datetime


class ErrorOut(BaseModel):
    codigo: str
    mensaje: str


class RelojIn(BaseModel):
    ahora: datetime | None = None
