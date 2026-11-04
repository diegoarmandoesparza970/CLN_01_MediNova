"""JornadaService: apertura de jornadas semanales, CU-03 (cancelar jornada y reagendar)."""
from __future__ import annotations

from uuid import uuid4

from src.domain.errores import CatalogoNoEncontrado, MedicoNoEncontrado
from src.domain.jornada import Jornada
from src.domain.reagendador import Reagendador
from src.domain.value_objects import MotivoDeCambio

from .agendamiento_service import AgendamientoService
from .comandos import AbrirJornadaCommand, CancelarJornadaCommand, ReagendarCitaCommand
from .dto import CitaAfectadaDto, CitaReagendadaDto
from .puertos import Reloj


class JornadaService:
    def __init__(self, uow_factory, reloj: Reloj, reagendador: Reagendador):
        self.uow_factory = uow_factory
        self.reloj = reloj
        self.reagendador = reagendador

    def abrir_jornada(self, cmd: AbrirJornadaCommand) -> str:
        with self.uow_factory() as u:
            if u.medicos.obtener(cmd.medico_id) is None:
                raise MedicoNoEncontrado(f"Médico {cmd.medico_id} no encontrado")
            if u.sucursales.obtener(cmd.sucursal_id) is None:
                raise CatalogoNoEncontrado(f"Sucursal {cmd.sucursal_id} no encontrada")
            agenda = u.agendas.obtener_por_medico_y_fecha(cmd.medico_id, cmd.franja.inicio.date())
            jornada = Jornada(str(uuid4()), cmd.sucursal_id, cmd.franja)
            agenda.abrir_jornada(jornada)
            AgendamientoService._guardar(u, agenda)
            u.confirmar()
        return jornada.id

    def cancelar_jornada(self, cmd: CancelarJornadaCommand) -> list[CitaAfectadaDto]:
        motivo = MotivoDeCambio(cmd.motivo)
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_medico_y_fecha(cmd.medico_id, cmd.fecha)
            afectadas = agenda.cancelar_jornada(cmd.sucursal_id, cmd.usuario, motivo, self.reloj.ahora())
            AgendamientoService._guardar(u, agenda)
            u.confirmar()
            return [CitaAfectadaDto(c.id, c.expediente, c.franja.inicio, c.estado.value) for c in afectadas]

    def reagendar_cita_afectada(self, cmd: ReagendarCitaCommand) -> CitaReagendadaDto:
        with self.uow_factory() as u:
            origen = u.agendas.obtener_por_cita(cmd.cita_id)
            medico = u.medicos.obtener(cmd.medico_id)
            if medico is None:
                raise MedicoNoEncontrado(f"Médico {cmd.medico_id} no encontrado")
            if u.sucursales.obtener(cmd.sucursal_id) is None:
                raise CatalogoNoEncontrado(f"Sucursal {cmd.sucursal_id} no encontrada")
            fecha = cmd.franja.inicio.date()
            if origen.medico_id == cmd.medico_id and origen.fecha == fecha:
                destino = origen  # misma agenda: una sola instancia para no perder cambios
            else:
                destino = u.agendas.obtener_por_medico_y_fecha(cmd.medico_id, fecha)
            nueva = self.reagendador.reagendar(origen, destino, cmd.cita_id, cmd.franja, cmd.sucursal_id,
                                               medico.limite_sobrecupo.valor, cmd.usuario,
                                               self.reloj.ahora(), str(uuid4()))
            AgendamientoService._guardar(u, *({id(a): a for a in (origen, destino)}.values()))
            u.confirmar()
            return CitaReagendadaDto(cmd.cita_id, nueva.id, nueva.estado.value)
