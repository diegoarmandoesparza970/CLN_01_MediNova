from __future__ import annotations

from src.application.puertos import EstadoDeNotificacion, Mensaje, Notificador, ResultadoDeNotificacion

from . import db


class NotificadorPorCanal(Notificador):
    """Confirma por el canal de origen (US-18).

    WhatsApp: modo 'simulado' registra el envío en la bandeja `notificaciones`; la API real de
    WhatsApp Business requiere credenciales de la clínica y queda como adaptador futuro.
    Teléfono y recepción los gestiona una persona: queda 'pendiente_gestion_manual' (LSP: no falla).
    """

    def __init__(self, session_factory, reloj, whatsapp_modo: str = "simulado"):
        self.session_factory = session_factory
        self.reloj = reloj
        self.whatsapp_modo = whatsapp_modo

    def enviar(self, mensaje: Mensaje) -> ResultadoDeNotificacion:
        if mensaje.canal == "whatsapp" and self.whatsapp_modo == "simulado":
            resultado = ResultadoDeNotificacion(EstadoDeNotificacion.ENVIADA, "WhatsApp (simulado)")
        else:
            resultado = ResultadoDeNotificacion(EstadoDeNotificacion.PENDIENTE_GESTION_MANUAL,
                                                "Recepción debe contactar al paciente")
        try:
            with self.session_factory() as s:
                s.add(db.NotificacionRow(cita_id=mensaje.cita_id, expediente=mensaje.expediente,
                                         canal=mensaje.canal, estado=resultado.estado.value,
                                         texto=mensaje.texto, creada_en=self.reloj.ahora()))
                s.commit()
        except Exception:  # noqa: BLE001 - el contrato exige no lanzar
            return ResultadoDeNotificacion(EstadoDeNotificacion.PENDIENTE_GESTION_MANUAL, "No se pudo registrar")
        return resultado
