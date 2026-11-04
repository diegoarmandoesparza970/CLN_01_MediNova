"""AtencionService: CU-02 (llegada y retraso), CU-05 (no-show), US-13 (cierre)."""
from __future__ import annotations

from src.domain.politicas import PoliticaDeNoShow
from src.domain.value_objects import ResultadoDeLlegada, Tolerancia

from .agendamiento_service import AgendamientoService
from .comandos import (
    CerrarConsultaCommand,
    MarcarNoAtendidaPorRetrasoCommand,
    MarcarNoShowCommand,
    RegistrarLlegadaCommand,
)
from .dto import CambioDeEstatusDto, ResultadoDeLlegadaDto
from .puertos import Reloj

MENSAJES = {
    ResultadoDeLlegada.A_TIEMPO: "Paciente presente a tiempo",
    ResultadoDeLlegada.CONSULTAR_MEDICO: "Retraso dentro de la tolerancia: consultar al médico si puede atenderlo",
    ResultadoDeLlegada.NO_ATENDIDA_POR_RETRASO: "Retraso mayor a la tolerancia: cita no atendida por retraso; se puede reagendar",
}


class AtencionService:
    def __init__(self, uow_factory, reloj: Reloj, tolerancia: Tolerancia,
                 politica_no_show: PoliticaDeNoShow, agendamiento: AgendamientoService):
        self.uow_factory = uow_factory
        self.reloj = reloj
        self.tolerancia = tolerancia
        self.politica_no_show = politica_no_show
        self.agendamiento = agendamiento

    def registrar_llegada(self, cmd: RegistrarLlegadaCommand) -> ResultadoDeLlegadaDto:
        ahora = cmd.hora_llegada or self.reloj.ahora()
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            resultado = agenda.registrar_llegada(cmd.cita_id, ahora, self.tolerancia)
            cita = agenda.obtener_cita(cmd.cita_id)
            if cmd.telefono is not None or cmd.actualiza_aseguradora:  # US-22
                paciente = u.pacientes.obtener_por_expediente(cita.expediente)
                paciente.actualizar_datos(telefono=cmd.telefono, aseguradora_id=cmd.aseguradora_id,
                                          cambia_aseguradora=cmd.actualiza_aseguradora)
                u.pacientes.guardar(paciente)
                u.vistos.append(paciente)
            self.agendamiento._guardar(u, agenda)
            u.confirmar()
            return ResultadoDeLlegadaDto(cmd.cita_id, resultado.value, cita.estado.value,
                                         MENSAJES[resultado], cita.llegada)

    def marcar_no_atendida_por_retraso(self, cmd: MarcarNoAtendidaPorRetrasoCommand) -> CambioDeEstatusDto:
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            agenda.marcar_no_atendida_por_retraso(cmd.cita_id, cmd.usuario, self.reloj.ahora())
            self.agendamiento._guardar(u, agenda)
            u.confirmar()
            return CambioDeEstatusDto(cmd.cita_id, agenda.obtener_cita(cmd.cita_id).estado.value)

    def marcar_no_show(self, cmd: MarcarNoShowCommand) -> CambioDeEstatusDto:
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            agenda.marcar_no_show(cmd.cita_id, cmd.usuario, self.reloj.ahora())
            expediente = agenda.obtener_cita(cmd.cita_id).expediente
            self.agendamiento._guardar(u, agenda)
            u.confirmar()
            total = u.agendas.contar_no_shows(expediente)
            alerta = self.politica_no_show.evaluar(total)
            return CambioDeEstatusDto(cmd.cita_id, agenda.obtener_cita(cmd.cita_id).estado.value,
                                      [alerta] if alerta else [])

    def cerrar_consulta(self, cmd: CerrarConsultaCommand) -> CambioDeEstatusDto:
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            agenda.cerrar_consulta(cmd.cita_id, cmd.cierre, cmd.usuario, self.reloj.ahora())
            self.agendamiento._guardar(u, agenda)
            avisos: list[str] = []
            if cmd.nueva_cita is not None:  # una sola transacción: cierre + próxima cita
                nueva = self.agendamiento.agendar_en(u, cmd.nueva_cita)
                avisos.append(f"Nueva cita {nueva.cita_id} ({nueva.estatus})")
                avisos.extend(nueva.advertencias)
            u.confirmar()
            return CambioDeEstatusDto(cmd.cita_id, agenda.obtener_cita(cmd.cita_id).estado.value, avisos)
