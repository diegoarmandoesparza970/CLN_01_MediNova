"""Domain Service: reagendar toca dos agendas, por eso no vive en una sola (US-09, US-11)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .agenda_medica import AgendaMedica
from .cita import Cita
from .estados import EstadoCita
from .value_objects import EstadoAutorizacion, FranjaHoraria


class Reagendador:
    def reagendar(self, origen: AgendaMedica, destino: AgendaMedica, cita_id: str,
                  franja: FranjaHoraria, sucursal_id: str, limite_sobrecupo: int,
                  usuario: str, ahora: datetime, nuevo_id: str) -> Cita:
        original = origen.obtener_cita(cita_id)
        nueva = replace(original, id=nuevo_id, medico_id=destino.medico_id, sucursal_id=sucursal_id,
                        franja=franja, estado=(EstadoCita.PENDIENTE_AUTORIZACION
                                               if original.autorizacion
                                               and original.autorizacion.estado == EstadoAutorizacion.PENDIENTE
                                               else EstadoCita.AGENDADA),
                        cita_origen_id=original.id, llegada=None, confirmacion=None, cierre=None,
                        reagendada_en=None)
        # Primero se valida el destino: si no hay lugar, el origen no cambia.
        destino.agendar(nueva, limite_sobrecupo, ahora)
        origen.marcar_reagendada(cita_id, usuario, ahora, nuevo_id)
        return nueva
