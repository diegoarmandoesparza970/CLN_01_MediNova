"""Value Objects: se definen por su valor y son inmutables (informe, sección 3)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .errores import DatosInvalidos


@dataclass(frozen=True)
class FranjaHoraria:
    """Intervalo [inicio, fin) dentro del cual se agenda una cita."""

    inicio: datetime
    fin: datetime

    def __post_init__(self):
        if self.fin <= self.inicio:
            raise DatosInvalidos("La franja debe tener duración positiva")

    def se_solapa(self, otra: "FranjaHoraria") -> bool:
        return self.inicio < otra.fin and otra.inicio < self.fin

    def contiene(self, otra: "FranjaHoraria") -> bool:
        return self.inicio <= otra.inicio and otra.fin <= self.fin

    @property
    def minutos(self) -> int:
        return int((self.fin - self.inicio).total_seconds() // 60)


@dataclass(frozen=True)
class LimiteDeSobrecupo:
    """Citas adicionales que un médico acepta en un horario ocupado (0 = ninguna)."""

    valor: int = 0

    def __post_init__(self):
        if self.valor < 0:
            raise DatosInvalidos("El límite de sobrecupo no puede ser negativo")


class ResultadoDeLlegada(str, Enum):
    A_TIEMPO = "a_tiempo"
    CONSULTAR_MEDICO = "consultar_medico"
    NO_ATENDIDA_POR_RETRASO = "no_atendida_por_retraso"


@dataclass(frozen=True)
class Tolerancia:
    """Margen de retraso (15 min por defecto, igual en las tres sucursales)."""

    minutos: int = 15

    def evaluar(self, programada: datetime, llegada: datetime) -> ResultadoDeLlegada:
        retraso = (llegada - programada).total_seconds() / 60
        if retraso <= 0:
            return ResultadoDeLlegada.A_TIEMPO
        if retraso <= self.minutos:
            return ResultadoDeLlegada.CONSULTAR_MEDICO
        return ResultadoDeLlegada.NO_ATENDIDA_POR_RETRASO


class EstadoAutorizacion(str, Enum):
    PENDIENTE = "pendiente"
    OTORGADA = "otorgada"
    NO_AUTORIZADA = "no_autorizada"


@dataclass(frozen=True)
class Autorizacion:
    estado: EstadoAutorizacion
    numero: str | None = None


class RespuestaDeConfirmacion(str, Enum):
    CONFIRMADA = "confirmada"
    RECHAZADA = "rechazada"
    SIN_RESPUESTA = "sin_respuesta"


@dataclass(frozen=True)
class Confirmacion:
    fecha_envio: datetime
    canal: str
    respuesta: RespuestaDeConfirmacion = RespuestaDeConfirmacion.SIN_RESPUESTA


class CanalDeSolicitud(str, Enum):
    TELEFONO = "telefono"
    WHATSAPP = "whatsapp"
    RECEPCION = "recepcion"


@dataclass(frozen=True)
class Contacto:
    telefono: str
    correo: str = ""

    def __post_init__(self):
        digitos = re.sub(r"\D", "", self.telefono or "")
        if len(digitos) < 10:
            raise DatosInvalidos("El teléfono debe tener al menos 10 dígitos")
        if self.correo and "@" not in self.correo:
            raise DatosInvalidos("Correo inválido")

    @property
    def telefono_normalizado(self) -> str:
        return re.sub(r"\D", "", self.telefono)


@dataclass(frozen=True)
class NumeroDeExpediente:
    valor: str

    def __post_init__(self):
        if not self.valor or not self.valor.strip():
            raise DatosInvalidos("Expediente vacío")


@dataclass(frozen=True)
class MotivoDeCambio:
    """Motivo obligatorio de cualquier cancelación o modificación (US-17)."""

    texto: str

    def __post_init__(self):
        if not self.texto or not self.texto.strip():
            raise DatosInvalidos("El motivo es obligatorio")


@dataclass(frozen=True)
class CierreDeConsulta:
    """Resultado de la consulta que registra recepción (US-13)."""

    receta: str = ""
    estudios: tuple[str, ...] = ()
    requiere_nueva_cita: bool = False


def sumar_horas(fecha: datetime, horas: int) -> datetime:
    return fecha + timedelta(hours=horas)
