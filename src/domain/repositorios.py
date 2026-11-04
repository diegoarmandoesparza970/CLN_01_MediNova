"""Puertos de persistencia en términos del dominio (informe, sección 5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from .agenda_medica import AgendaMedica
from .catalogos import Aseguradora, Especialidad, Medico, Paciente, Sucursal
from .eventos import RegistroDeAuditoria
from .value_objects import FranjaHoraria


class AgendaMedicaRepository(ABC):
    @abstractmethod
    def obtener_por_medico_y_fecha(self, medico_id: str, fecha: date) -> AgendaMedica:
        """Devuelve la agenda; si no existe, una agenda vacía con version 0."""

    @abstractmethod
    def obtener_por_cita(self, cita_id: str) -> AgendaMedica: ...

    @abstractmethod
    def guardar(self, agenda: AgendaMedica) -> None:
        """Lanza ConflictoDeVersion si otra transacción guardó antes."""

    @abstractmethod
    def franjas_activas_de_paciente(self, expediente: str, fecha: date) -> list[FranjaHoraria]: ...

    @abstractmethod
    def contar_no_shows(self, expediente: str) -> int: ...

    @abstractmethod
    def listar_por_rango(self, desde: date, hasta: date) -> list[AgendaMedica]: ...


class PacienteRepository(ABC):
    @abstractmethod
    def obtener_por_expediente(self, numero: str) -> Paciente | None: ...

    @abstractmethod
    def buscar_por_telefono(self, telefono: str) -> Paciente | None: ...

    @abstractmethod
    def agregar(self, paciente: Paciente) -> None: ...

    @abstractmethod
    def guardar(self, paciente: Paciente) -> None: ...

    @abstractmethod
    def siguiente_numero_de_expediente(self) -> str: ...


class MedicoRepository(ABC):
    @abstractmethod
    def obtener(self, medico_id: str) -> Medico | None: ...

    @abstractmethod
    def guardar(self, medico: Medico) -> None: ...

    @abstractmethod
    def listar(self) -> list[Medico]: ...


class AseguradoraRepository(ABC):
    @abstractmethod
    def obtener(self, aseguradora_id: str) -> Aseguradora | None: ...

    @abstractmethod
    def guardar(self, aseguradora: Aseguradora) -> None: ...

    @abstractmethod
    def listar(self) -> list[Aseguradora]: ...


class SucursalRepository(ABC):
    @abstractmethod
    def obtener(self, sucursal_id: str) -> Sucursal | None: ...

    @abstractmethod
    def guardar(self, sucursal: Sucursal) -> None: ...

    @abstractmethod
    def listar(self) -> list[Sucursal]: ...


class EspecialidadRepository(ABC):
    @abstractmethod
    def obtener(self, especialidad_id: str) -> Especialidad | None: ...

    @abstractmethod
    def guardar(self, especialidad: Especialidad) -> None: ...

    @abstractmethod
    def listar(self) -> list[Especialidad]: ...


class RegistroDeAuditoriaRepository(ABC):
    @abstractmethod
    def agregar(self, registro: RegistroDeAuditoria) -> None: ...
