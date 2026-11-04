"""Handlers de Query: delegan en lectores; no abren Unit of Work de escritura."""
from __future__ import annotations

from src.domain.politicas import PoliticaDeNoShow

from . import consultas as q
from .lectores import LectorDeConsultas


class ConsultaService:
    def __init__(self, lector: LectorDeConsultas, politica_no_show: PoliticaDeNoShow):
        self.lector = lector
        self.politica = politica_no_show

    def disponibilidad(self, c): return self.lector.disponibilidad(c)
    def citas_afectadas(self, c): return self.lector.citas_afectadas(c)
    def reporte(self, c): return self.lector.reporte(c)
    def citas(self, c): return self.lector.citas(c)
    def cita(self, cita_id): return self.lector.cita(cita_id)
    def auditoria(self, cita_id=None): return self.lector.auditoria(cita_id)
    def notificaciones(self, limite=50): return self.lector.notificaciones(limite)

    def historial_no_shows(self, c: q.ConsultarHistorialDeNoShows):
        vm = self.lector.historial_no_shows(c)
        if vm is not None:
            vm.alerta = self.politica.evaluar(vm.total)
        return vm
