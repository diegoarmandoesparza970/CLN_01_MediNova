"""Puertos de lectura (lado Query de CQRS). No pasan por el dominio ni por la UoW."""
from __future__ import annotations

from abc import ABC, abstractmethod

from . import consultas as q


class LectorDeConsultas(ABC):
    @abstractmethod
    def disponibilidad(self, consulta: q.ConsultarDisponibilidadDelMedico) -> list[q.DisponibilidadDelMedicoVM]: ...

    @abstractmethod
    def citas_afectadas(self, consulta: q.ConsultarCitasAfectadas) -> list[q.CitaAfectadaVM]: ...

    @abstractmethod
    def historial_no_shows(self, consulta: q.ConsultarHistorialDeNoShows) -> q.HistorialNoShowsVM | None: ...

    @abstractmethod
    def reporte(self, consulta: q.ObtenerReporteConsolidado) -> q.ReporteConsolidadoVM: ...

    @abstractmethod
    def citas(self, consulta: q.ConsultarCitas) -> list[q.CitaVM]: ...

    @abstractmethod
    def cita(self, cita_id: str) -> q.CitaVM | None: ...

    @abstractmethod
    def auditoria(self, cita_id: str | None) -> list[q.RegistroAuditoriaVM]: ...

    @abstractmethod
    def notificaciones(self, limite: int) -> list[q.NotificacionVM]: ...
