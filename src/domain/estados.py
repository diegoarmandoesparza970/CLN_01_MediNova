"""State Machine del ciclo de vida de la Cita (US-07, US-09, US-12, US-13, US-20).

La tabla de transiciones es la única fuente de verdad: el diagrama de estados de
la documentación se genera desde ella (ver `a_mermaid`).
"""
from __future__ import annotations

from enum import Enum

from .errores import TransicionDeEstatusInvalida


class EstadoCita(str, Enum):
    AGENDADA = "agendada"
    PENDIENTE_AUTORIZACION = "pendiente_autorizacion"
    PRESENTE = "presente"
    ATENDIDA = "atendida"
    NO_SHOW = "no_show"
    NO_ATENDIDA_POR_RETRASO = "no_atendida_por_retraso"
    CANCELADA = "cancelada"
    AFECTADA = "afectada"
    REAGENDADA = "reagendada"


class Disparador(str, Enum):
    REGISTRAR_AUTORIZACION = "registrar_autorizacion"
    PAGAR_COMO_PARTICULAR = "pagar_como_particular"
    REGISTRAR_LLEGADA = "registrar_llegada"
    MARCAR_NO_ATENDIDA_POR_RETRASO = "marcar_no_atendida_por_retraso"
    MARCAR_NO_SHOW = "marcar_no_show"
    CERRAR_CONSULTA = "cerrar_consulta"
    CANCELAR = "cancelar"
    AFECTAR_POR_JORNADA = "afectar_por_jornada"
    REAGENDAR = "reagendar"


E, D = EstadoCita, Disparador

TRANSICIONES: dict[tuple[EstadoCita, Disparador], EstadoCita] = {
    (E.PENDIENTE_AUTORIZACION, D.REGISTRAR_AUTORIZACION): E.AGENDADA,
    (E.PENDIENTE_AUTORIZACION, D.PAGAR_COMO_PARTICULAR): E.AGENDADA,
    (E.PENDIENTE_AUTORIZACION, D.MARCAR_NO_SHOW): E.NO_SHOW,
    (E.PENDIENTE_AUTORIZACION, D.CANCELAR): E.CANCELADA,
    (E.PENDIENTE_AUTORIZACION, D.AFECTAR_POR_JORNADA): E.AFECTADA,
    (E.AGENDADA, D.REGISTRAR_LLEGADA): E.PRESENTE,
    (E.AGENDADA, D.MARCAR_NO_ATENDIDA_POR_RETRASO): E.NO_ATENDIDA_POR_RETRASO,
    (E.AGENDADA, D.MARCAR_NO_SHOW): E.NO_SHOW,
    (E.AGENDADA, D.CANCELAR): E.CANCELADA,
    (E.AGENDADA, D.AFECTAR_POR_JORNADA): E.AFECTADA,
    (E.PRESENTE, D.CERRAR_CONSULTA): E.ATENDIDA,
    (E.PRESENTE, D.MARCAR_NO_ATENDIDA_POR_RETRASO): E.NO_ATENDIDA_POR_RETRASO,
    (E.PRESENTE, D.CANCELAR): E.CANCELADA,
    (E.AFECTADA, D.REAGENDAR): E.REAGENDADA,
    (E.AFECTADA, D.CANCELAR): E.CANCELADA,
    (E.NO_ATENDIDA_POR_RETRASO, D.REAGENDAR): E.REAGENDADA,
    (E.NO_ATENDIDA_POR_RETRASO, D.CANCELAR): E.CANCELADA,
}

ESTADOS_FINALES = frozenset(
    {E.ATENDIDA, E.NO_SHOW, E.CANCELADA, E.REAGENDADA}
)
ESTADOS_QUE_BLOQUEAN_FRANJA = frozenset(
    {E.AGENDADA, E.PENDIENTE_AUTORIZACION, E.PRESENTE, E.ATENDIDA}
)


class MaquinaDeEstadosDeCita:
    """Aplica disparadores validando la tabla de transiciones."""

    @staticmethod
    def siguiente(actual: EstadoCita, disparador: Disparador) -> EstadoCita:
        try:
            return TRANSICIONES[(actual, disparador)]
        except KeyError:
            raise TransicionDeEstatusInvalida(
                f"No se puede '{disparador.value}' una cita en estatus '{actual.value}'"
            ) from None

    @staticmethod
    def permitidos(actual: EstadoCita) -> list[Disparador]:
        return [d for (e, d) in TRANSICIONES if e == actual]

    @staticmethod
    def a_mermaid() -> str:
        lineas = ["stateDiagram-v2", "    direction LR", f"    [*] --> {E.AGENDADA.value}: sin autorización requerida",
                  f"    [*] --> {E.PENDIENTE_AUTORIZACION.value}: aseguradora exige autorización"]
        for (origen, disp), destino in TRANSICIONES.items():
            lineas.append(f"    {origen.value} --> {destino.value}: {disp.value}")
        for final in sorted(ESTADOS_FINALES, key=lambda s: s.value):
            lineas.append(f"    {final.value} --> [*]")
        return "\n".join(lineas)
