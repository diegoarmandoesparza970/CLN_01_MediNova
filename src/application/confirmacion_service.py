"""ConfirmacionService: US-06 (recordatorio), US-18 (canal de origen), US-21 (liberar horario)."""
from __future__ import annotations

from datetime import timedelta

from src.domain.errores import DatosInvalidos
from src.domain.estados import EstadoCita
from src.domain.value_objects import MotivoDeCambio, RespuestaDeConfirmacion

from .agendamiento_service import AgendamientoService
from .comandos import EnviarConfirmacionesCommand, RegistrarRespuestaDeConfirmacionCommand
from .puertos import Mensaje, Notificador, Reloj

ACTIVAS = (EstadoCita.AGENDADA, EstadoCita.PENDIENTE_AUTORIZACION)


class ConfirmacionService:
    def __init__(self, uow_factory, reloj: Reloj, notificador: Notificador, limite_horas: int = 24):
        self.uow_factory = uow_factory
        self.reloj = reloj
        self.notificador = notificador
        self.limite_horas = limite_horas

    def enviar_confirmaciones(self, cmd: EnviarConfirmacionesCommand) -> list[dict]:
        ahora = self.reloj.ahora()
        pendientes: list[Mensaje] = []
        with self.uow_factory() as u:
            for agenda in u.agendas.listar_por_rango(cmd.fecha, cmd.fecha):
                cambio = False
                for c in agenda.citas:
                    if c.estado in ACTIVAS and c.confirmacion is None:
                        agenda.registrar_envio_de_confirmacion(c.id, c.canal, ahora)
                        paciente = u.pacientes.obtener_por_expediente(c.expediente)
                        pendientes.append(Mensaje(
                            c.id, c.expediente, paciente.contacto.telefono, c.canal,
                            f"MediNova: confirme su cita de mañana {c.franja.inicio:%H:%M}. Responda SI o NO."))
                        cambio = True
                if cambio:
                    AgendamientoService._guardar(u, agenda)
            u.confirmar()
        resultados = []
        for m in pendientes:  # después de confirmar; un fallo no deshace nada
            r = self.notificador.enviar(m)
            resultados.append({"cita_id": m.cita_id, "canal": m.canal, "estado": r.estado.value})
        return resultados

    def registrar_respuesta(self, cmd: RegistrarRespuestaDeConfirmacionCommand) -> dict:
        try:
            respuesta = RespuestaDeConfirmacion(cmd.respuesta)
        except ValueError:
            raise DatosInvalidos("Respuesta inválida: confirmada, rechazada o sin_respuesta") from None
        ahora = self.reloj.ahora()
        with self.uow_factory() as u:
            agenda = u.agendas.obtener_por_cita(cmd.cita_id)
            agenda.registrar_respuesta_de_confirmacion(cmd.cita_id, respuesta, ahora)
            if respuesta == RespuestaDeConfirmacion.RECHAZADA:  # se libera el horario
                agenda.cancelar(cmd.cita_id, cmd.usuario, MotivoDeCambio("El paciente rechazó la confirmación"), ahora)
            AgendamientoService._guardar(u, agenda)
            u.confirmar()
            return {"cita_id": cmd.cita_id, "estatus": agenda.obtener_cita(cmd.cita_id).estado.value,
                    "respuesta": respuesta.value}

    def liberar_sin_confirmacion(self) -> list[str]:
        """US-21: sin respuesta tras `limite_horas`, se libera el horario con auditoría."""
        ahora = self.reloj.ahora()
        liberadas: list[str] = []
        with self.uow_factory() as u:
            for agenda in u.agendas.listar_por_rango(ahora.date(), ahora.date() + timedelta(days=60)):
                cambio = False
                for c in agenda.citas:
                    if (c.estado in ACTIVAS and c.confirmacion is not None
                            and c.confirmacion.respuesta == RespuestaDeConfirmacion.SIN_RESPUESTA
                            and c.franja.inicio > ahora
                            and ahora - c.confirmacion.fecha_envio >= timedelta(hours=self.limite_horas)):
                        agenda.cancelar(c.id, "sistema", MotivoDeCambio(
                            f"Sin confirmación en {self.limite_horas} h: horario liberado"), ahora)
                        liberadas.append(c.id)
                        cambio = True
                if cambio:
                    AgendamientoService._guardar(u, agenda)
            u.confirmar()
        return liberadas
