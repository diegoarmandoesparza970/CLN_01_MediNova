"""AgendamientoService: CU-01 (agendar) y CU-04 (cancelar / modificar), US-12."""
from __future__ import annotations

from uuid import uuid4

from src.domain.cita import Cita
from src.domain.errores import (
    CatalogoNoEncontrado,
    CitaSolapadaDelPaciente,
    ConflictoDeVersion,
    DatosInvalidos,
    HorarioNoDisponible,
    MedicoNoEncontrado,
    PacienteNoEncontrado,
)
from src.domain.especificaciones import PacienteSinCitaSolapada
from src.domain.estados import EstadoCita
from src.domain.politicas import PoliticaDeAutorizacion, PoliticaDeNoShow
from src.domain.value_objects import Autorizacion, EstadoAutorizacion, MotivoDeCambio

from .comandos import (
    AgendarCitaCommand,
    CancelarCitaCommand,
    ModificarCitaCommand,
    PagarComoParticularCommand,
    RegistrarAutorizacionCommand,
)
from .dto import CambioDeEstatusDto, CitaAgendadaDto
from .puertos import Reloj


class AgendamientoService:
    def __init__(self, uow_factory, politica_autorizacion: PoliticaDeAutorizacion,
                 politica_no_show: PoliticaDeNoShow, reloj: Reloj):
        self.uow_factory = uow_factory
        self.politica_autorizacion = politica_autorizacion
        self.politica_no_show = politica_no_show
        self.reloj = reloj

    # --------------------------------------------------------------- CU-01
    def agendar_cita(self, cmd: AgendarCitaCommand) -> CitaAgendadaDto:
        with self.uow_factory() as u:
            dto = self.agendar_en(u, cmd)
            u.confirmar()
        return dto

    def agendar_en(self, u, cmd: AgendarCitaCommand) -> CitaAgendadaDto:
        """Reutilizable dentro de otra transacción (p. ej. la nueva cita al cerrar consulta)."""
        ahora = self.reloj.ahora()
        paciente = u.pacientes.obtener_por_expediente(cmd.expediente)
        if paciente is None:
            raise PacienteNoEncontrado(f"Paciente {cmd.expediente} no encontrado")
        medico = u.medicos.obtener(cmd.medico_id)
        if medico is None:
            raise MedicoNoEncontrado(f"Médico {cmd.medico_id} no encontrado")
        if u.sucursales.obtener(cmd.sucursal_id) is None:
            raise CatalogoNoEncontrado(f"Sucursal {cmd.sucursal_id} no encontrada")
        if cmd.especialidad and medico.especialidades and cmd.especialidad not in medico.especialidades:
            raise DatosInvalidos(f"El médico no atiende la especialidad {cmd.especialidad}")
        aseguradora = None
        if cmd.aseguradora_id:
            aseguradora = u.aseguradoras.obtener(cmd.aseguradora_id)
            if aseguradora is None:
                raise CatalogoNoEncontrado(f"Aseguradora {cmd.aseguradora_id} no encontrada")
        if cmd.franja.inicio < ahora:
            raise DatosInvalidos("No se puede agendar una cita en el pasado")

        fecha = cmd.franja.inicio.date()
        franjas = tuple(u.agendas.franjas_activas_de_paciente(cmd.expediente, fecha))
        if not PacienteSinCitaSolapada(franjas).es_satisfecha_por(cmd.franja):
            raise CitaSolapadaDelPaciente("El paciente ya tiene una cita en ese horario (otra sucursal o médico)")

        advertencias: list[str] = []
        autorizacion = None
        if self.politica_autorizacion.requiere(aseguradora):
            if cmd.numero_autorizacion and cmd.numero_autorizacion.strip():
                autorizacion = Autorizacion(EstadoAutorizacion.OTORGADA, cmd.numero_autorizacion.strip())
            else:
                autorizacion = Autorizacion(EstadoAutorizacion.PENDIENTE)
                horas = aseguradora.anticipacion_horas
                if horas and (cmd.franja.inicio - ahora).total_seconds() < horas * 3600:
                    advertencias.append(f"La aseguradora pide autorización con {horas} h de anticipación")
        estado = (EstadoCita.PENDIENTE_AUTORIZACION
                  if autorizacion and autorizacion.estado == EstadoAutorizacion.PENDIENTE
                  else EstadoCita.AGENDADA)

        total = u.agendas.contar_no_shows(cmd.expediente)
        alerta = self.politica_no_show.evaluar(total)
        if alerta:
            advertencias.append(alerta)

        agenda = u.agendas.obtener_por_medico_y_fecha(cmd.medico_id, fecha)
        cita = Cita(str(uuid4()), cmd.expediente, cmd.medico_id, cmd.sucursal_id, cmd.franja,
                    cmd.especialidad, cmd.motivo, cmd.canal, cmd.aseguradora_id, autorizacion, estado)
        agenda.agendar(cita, medico.limite_sobrecupo.valor, ahora)
        self._guardar(u, agenda)
        return CitaAgendadaDto(cita.id, cita.estado.value,
                               autorizacion.estado.value if autorizacion else None, advertencias)

    @staticmethod
    def _guardar(u, *agendas):
        """Un conflicto de versión significa que otra recepcionista reservó antes (US-05)."""
        try:
            for a in agendas:
                u.agendas.guardar(a)
        except ConflictoDeVersion as ex:
            raise HorarioNoDisponible("Horario no disponible: otra recepción reservó al mismo tiempo") from ex

    # --------------------------------------------------------------- CU-04
    def cancelar_cita(self, cmd: CancelarCitaCommand) -> CambioDeEstatusDto:
        motivo = MotivoDeCambio(cmd.motivo)
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            agenda.cancelar(cmd.cita_id, cmd.usuario, motivo, self.reloj.ahora())
            self._guardar(u, agenda)
            u.confirmar()
        return CambioDeEstatusDto(cmd.cita_id, EstadoCita.CANCELADA.value)

    def modificar_cita(self, cmd: ModificarCitaCommand) -> CambioDeEstatusDto:
        motivo = MotivoDeCambio(cmd.motivo)
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            medico = u.medicos.obtener(agenda.medico_id)
            if u.sucursales.obtener(cmd.sucursal_id) is None:
                raise CatalogoNoEncontrado(f"Sucursal {cmd.sucursal_id} no encontrada")
            cita = agenda.modificar(cmd.cita_id, cmd.franja, cmd.sucursal_id,
                                    medico.limite_sobrecupo.valor, cmd.usuario, motivo, self.reloj.ahora())
            self._guardar(u, agenda)
            u.confirmar()
        return CambioDeEstatusDto(cmd.cita_id, cita.estado.value)

    # ---------------------------------------------------------------- US-12
    def registrar_autorizacion(self, cmd: RegistrarAutorizacionCommand) -> CambioDeEstatusDto:
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            cita = agenda.registrar_autorizacion(cmd.cita_id, cmd.numero, cmd.usuario, self.reloj.ahora())
            self._guardar(u, agenda)
            u.confirmar()
        return CambioDeEstatusDto(cmd.cita_id, cita.estado.value)

    def pagar_como_particular(self, cmd: PagarComoParticularCommand) -> CambioDeEstatusDto:
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            cita = agenda.pagar_como_particular(cmd.cita_id, cmd.usuario, self.reloj.ahora())
            self._guardar(u, agenda)
            u.confirmar()
        return CambioDeEstatusDto(cmd.cita_id, cita.estado.value)
