"""Puertos que la infraestructura implementa (SOLID-D)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Reloj(ABC):
    @abstractmethod
    def ahora(self) -> datetime: ...


class EstadoDeNotificacion(str, Enum):
    ENVIADA = "enviada"
    PENDIENTE_GESTION_MANUAL = "pendiente_gestion_manual"


@dataclass(frozen=True)
class Mensaje:
    cita_id: str | None
    expediente: str
    telefono: str
    canal: str
    texto: str


@dataclass(frozen=True)
class ResultadoDeNotificacion:
    estado: EstadoDeNotificacion
    detalle: str = ""


class Notificador(ABC):
    """Contrato (LSP): ninguna implementación lanza error por su canal; devuelve un
    resultado y, si no puede enviar, deja la gestión manual a recepción."""

    @abstractmethod
    def enviar(self, mensaje: Mensaje) -> ResultadoDeNotificacion: ...
