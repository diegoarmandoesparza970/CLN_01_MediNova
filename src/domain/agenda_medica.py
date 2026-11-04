"""Aggregate raíz AgendaMedica: agenda de un médico en una fecha, en todas sus sucursales.

Es el único lugar que garantiza que no haya citas duplicadas entre sucursales
(US-05, ADR-002). Toda mutación recibe `ahora` para no depender del reloj (SOLID-D).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime

from . import eventos as ev
from .cita import Cita
from .errores import (
    CitaNoEncontrada,
    DatosInvalidos,
    FranjaFueraDeJornada,
    HorarioNoDisponible,
    JornadaTraslapada,
    SobrecupoExcedido,
    TransicionDeEstatusInvalida,
)
from .especificaciones import (
    CitaDelMedicoYFecha,
    CitaEnEstado,
    ContextoDeAgendado,
    FranjaDentroDeJornadaVigente,
    HorarioLibre,
    HoraYaPaso,
    JornadaSinTraslape,
    LlegadaEnElDiaDeLaCita,
    SobrecupoDisponible,
)
from .estados import Disparador, EstadoCita
from .jornada import Jornada
from .value_objects import (
    Autorizacion,
    CierreDeConsulta,
    Confirmacion,
    EstadoAutorizacion,
    FranjaHoraria,
    MotivoDeCambio,
    RespuestaDeConfirmacion,
    ResultadoDeLlegada,
    Tolerancia,
)


@dataclass
class AgendaMedica:
    medico_id: str
    fecha: date
    jornadas: list[Jornada] = field(default_factory=list)
    citas: list[Cita] = field(default_factory=list)
    version: int = 0  # 0 = aún no persistida; control de concurrencia optimista
    eventos: list[ev.Evento] = field(default_factory=list, repr=False)

    # ---------------------------------------------------------------- consulta
    def obtener_cita(self, cita_id: str) -> Cita:
        for c in self.citas:
            if c.id == cita_id:
                return c
        raise CitaNoEncontrada(f"Cita {cita_id} no encontrada")

    def recoger_eventos(self) -> list[ev.Evento]:
        e, self.eventos = self.eventos, []
        return e

    def _activas(self, excluir: str | None = None) -> tuple[Cita, ...]:
        return tuple(c for c in self.citas if c.bloquea_franja and c.id != excluir)

    # ---------------------------------------------------------------- jornadas
    def abrir_jornada(self, jornada: Jornada):
        """Los horarios cambian cada semana: se abren jornadas por sucursal (BRD)."""
        if jornada.franja.inicio.date() != self.fecha or jornada.franja.fin.date() != self.fecha:
            raise DatosInvalidos("La jornada debe iniciar y terminar en la fecha de la agenda")
        if not JornadaSinTraslape(tuple(self.jornadas)).es_satisfecha_por(jornada):
            raise JornadaTraslapada("El médico ya tiene una jornada en ese horario (otra sucursal)")
        self.jornadas.append(jornada)

    # ----------------------------------------------------------------- agendar
    def _validar_ocupacion(self, cita: Cita, limite: int, excluir: str | None = None):
        ctx = ContextoDeAgendado(cita, self.fecha, self.medico_id, tuple(self.jornadas),
                                 self._activas(excluir), limite)
        if not CitaDelMedicoYFecha().es_satisfecha_por(ctx):
            raise FranjaFueraDeJornada("Médico o fecha distintos a los de la agenda")
        if not FranjaDentroDeJornadaVigente().es_satisfecha_por(ctx):
            raise FranjaFueraDeJornada("La franja está fuera de una jornada vigente de esa sucursal")
        if not (HorarioLibre() | SobrecupoDisponible()).es_satisfecha_por(ctx):
            if limite > 0:
                raise SobrecupoExcedido(f"Se alcanzó el límite de sobrecupo del médico ({limite})")
            raise HorarioNoDisponible("Horario no disponible: el médico ya tiene una cita en esa franja")

    def agendar(self, cita: Cita, limite_sobrecupo: int, ahora: datetime) -> Cita:
        if any(c.id == cita.id for c in self.citas):
            raise HorarioNoDisponible("Identificador de cita repetido")
        self._validar_ocupacion(cita, limite_sobrecupo)
        cita.creada_en = ahora
        self.citas.append(cita)
        self.eventos.append(ev.CitaAgendada(cita.id, cita.expediente, "", ahora,
                                            {"canal": cita.canal, "expediente": cita.expediente,
                                             "inicio": cita.franja.inicio.isoformat()}))
        return cita

    # ------------------------------------------------- cancelar / modificar (CU-04)
    def cancelar(self, cita_id: str, usuario: str, motivo: MotivoDeCambio, ahora: datetime) -> Cita:
        cita = self.obtener_cita(cita_id)
        cita.aplicar(Disparador.CANCELAR)
        self.eventos.append(ev.CitaCancelada(cita_id, usuario, motivo.texto, ahora))
        return cita

    def modificar(self, cita_id: str, nueva_franja: FranjaHoraria, nueva_sucursal: str,
                  limite_sobrecupo: int, usuario: str, motivo: MotivoDeCambio, ahora: datetime) -> Cita:
        cita = self.obtener_cita(cita_id)
        if not CitaEnEstado((EstadoCita.AGENDADA, EstadoCita.PENDIENTE_AUTORIZACION)).es_satisfecha_por(cita):
            raise TransicionDeEstatusInvalida("Solo se modifican citas agendadas o pendientes de autorización")
        propuesta = replace(cita, franja=nueva_franja, sucursal_id=nueva_sucursal)
        self._validar_ocupacion(propuesta, limite_sobrecupo, excluir=cita_id)  # no cambia nada si falla
        anterior = cita.franja.inicio.isoformat()
        cita.franja, cita.sucursal_id = nueva_franja, nueva_sucursal
        self.eventos.append(ev.CitaModificada(cita_id, usuario, motivo.texto, ahora,
                                              {"antes": anterior, "despues": nueva_franja.inicio.isoformat()}))
        return cita

    # -------------------------------------------------- autorización (US-12)
    def registrar_autorizacion(self, cita_id: str, numero: str, usuario: str, ahora: datetime) -> Cita:
        if not numero or not numero.strip():
            raise DatosInvalidos("El número de autorización es obligatorio")
        cita = self.obtener_cita(cita_id)
        cita.aplicar(Disparador.REGISTRAR_AUTORIZACION)
        cita.autorizacion = Autorizacion(EstadoAutorizacion.OTORGADA, numero.strip())
        self.eventos.append(ev.AutorizacionRegistrada(cita_id, usuario, "", ahora))
        return cita

    def pagar_como_particular(self, cita_id: str, usuario: str, ahora: datetime) -> Cita:
        """Q13: sin autorización el paciente puede pagar como particular."""
        cita = self.obtener_cita(cita_id)
        cita.aplicar(Disparador.PAGAR_COMO_PARTICULAR)
        cita.aseguradora_id = None
        cita.autorizacion = None
        self.eventos.append(ev.AutorizacionRegistrada(cita_id, usuario, "pago como particular", ahora))
        return cita

    # ------------------------------------------------ confirmación (US-06, US-21)
    def registrar_envio_de_confirmacion(self, cita_id: str, canal: str, ahora: datetime):
        cita = self.obtener_cita(cita_id)
        cita.confirmacion = Confirmacion(ahora, canal)

    def registrar_respuesta_de_confirmacion(self, cita_id: str, respuesta: RespuestaDeConfirmacion,
                                            ahora: datetime):
        cita = self.obtener_cita(cita_id)
        if cita.confirmacion is None:
            raise TransicionDeEstatusInvalida("La confirmación aún no se ha enviado")
        cita.confirmacion = replace(cita.confirmacion, respuesta=respuesta)
        self.eventos.append(ev.ConfirmacionRegistrada(cita_id, "paciente", respuesta.value, ahora))

    # ------------------------------------------------------- atención (CU-02)
    def registrar_llegada(self, cita_id: str, ahora: datetime, tolerancia: Tolerancia) -> ResultadoDeLlegada:
        cita = self.obtener_cita(cita_id)
        if cita.estado == EstadoCita.PENDIENTE_AUTORIZACION:
            raise TransicionDeEstatusInvalida(
                "Autorización pendiente: registrar el número, cobrar como particular o reagendar")
        if not LlegadaEnElDiaDeLaCita(ahora).es_satisfecha_por(cita):
            raise TransicionDeEstatusInvalida("La llegada solo se registra el día de la cita")
        resultado = tolerancia.evaluar(cita.franja.inicio, ahora)
        if resultado == ResultadoDeLlegada.NO_ATENDIDA_POR_RETRASO:
            cita.aplicar(Disparador.MARCAR_NO_ATENDIDA_POR_RETRASO)
            self.eventos.append(ev.CitaNoAtendidaPorRetraso(cita_id, "recepcion", "", ahora))
        else:
            cita.aplicar(Disparador.REGISTRAR_LLEGADA)
            cita.llegada = ahora
            self.eventos.append(ev.LlegadaRegistrada(cita_id, "recepcion", "", ahora,
                                                     {"resultado": resultado.value}))
        return resultado

    def marcar_no_atendida_por_retraso(self, cita_id: str, usuario: str, ahora: datetime):
        cita = self.obtener_cita(cita_id)
        cita.aplicar(Disparador.MARCAR_NO_ATENDIDA_POR_RETRASO)
        self.eventos.append(ev.CitaNoAtendidaPorRetraso(cita_id, usuario, "", ahora))

    def marcar_no_show(self, cita_id: str, usuario: str, ahora: datetime):
        cita = self.obtener_cita(cita_id)
        if not HoraYaPaso(ahora).es_satisfecha_por(cita):
            raise TransicionDeEstatusInvalida("Solo es no-show una cita cuya hora ya pasó")
        cita.aplicar(Disparador.MARCAR_NO_SHOW)
        self.eventos.append(ev.CitaMarcadaComoNoShow(cita_id, usuario, "", ahora,
                                                     {"expediente": cita.expediente}))

    def cerrar_consulta(self, cita_id: str, cierre: CierreDeConsulta, usuario: str, ahora: datetime):
        cita = self.obtener_cita(cita_id)
        cita.aplicar(Disparador.CERRAR_CONSULTA)
        cita.cierre = cierre
        self.eventos.append(ev.ConsultaCerrada(cita_id, usuario, "", ahora))

    # ---------------------------------------------- jornada cancelada (CU-03)
    def cancelar_jornada(self, sucursal_id: str | None, usuario: str, motivo: MotivoDeCambio,
                         ahora: datetime) -> list[Cita]:
        """Cancela la jornada de una sucursal o, si no se indica, todas las del día."""
        objetivo = [j for j in self.jornadas
                    if not j.cancelada and (sucursal_id is None or j.sucursal_id == sucursal_id)]
        if not objetivo:
            raise FranjaFueraDeJornada("No hay jornada vigente que cancelar")
        sucursales = set()
        for j in objetivo:
            j.cancelada, j.cancelada_en = True, ahora
            sucursales.add(j.sucursal_id)
        afectadas = []
        for c in sorted(self.citas, key=lambda c: c.franja.inicio):  # la más próxima primero
            if c.sucursal_id in sucursales and CitaEnEstado(
                    (EstadoCita.AGENDADA, EstadoCita.PENDIENTE_AUTORIZACION)).es_satisfecha_por(c):
                c.aplicar(Disparador.AFECTAR_POR_JORNADA)
                afectadas.append(c)
                self.eventos.append(ev.CitaAfectadaPorJornada(c.id, usuario, motivo.texto, ahora))
        self.eventos.append(ev.JornadaCancelada(None, usuario, motivo.texto, ahora,
                                                {"sucursales": sorted(sucursales),
                                                 "citas_afectadas": [c.id for c in afectadas]}))
        return afectadas

    def marcar_reagendada(self, cita_id: str, usuario: str, ahora: datetime, nueva_cita_id: str):
        cita = self.obtener_cita(cita_id)
        cita.aplicar(Disparador.REAGENDAR)
        cita.reagendada_en = ahora
        self.eventos.append(ev.CitaReagendada(cita_id, usuario, f"Reagendada como {nueva_cita_id}", ahora,
                                              {"nueva_cita_id": nueva_cita_id}))
