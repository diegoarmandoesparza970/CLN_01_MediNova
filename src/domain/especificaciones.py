"""Patrón Specification: reglas de negocio componibles con &, | y ~.

Cada regla del BRD/US se expresa como una especificación pequeña y probable por
separado; el Aggregate las compone (ADR-006).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, TypeVar

from .cita import Cita
from .estados import EstadoCita
from .jornada import Jornada
from .value_objects import FranjaHoraria

T = TypeVar("T")


class Especificacion(ABC, Generic[T]):
    @abstractmethod
    def es_satisfecha_por(self, candidato: T) -> bool: ...

    def __and__(self, otra: "Especificacion[T]") -> "Especificacion[T]":
        return _Y(self, otra)

    def __or__(self, otra: "Especificacion[T]") -> "Especificacion[T]":
        return _O(self, otra)

    def __invert__(self) -> "Especificacion[T]":
        return _No(self)


@dataclass(frozen=True)
class _Y(Especificacion[T]):
    a: Especificacion
    b: Especificacion

    def es_satisfecha_por(self, candidato):
        return self.a.es_satisfecha_por(candidato) and self.b.es_satisfecha_por(candidato)


@dataclass(frozen=True)
class _O(Especificacion[T]):
    a: Especificacion
    b: Especificacion

    def es_satisfecha_por(self, candidato):
        return self.a.es_satisfecha_por(candidato) or self.b.es_satisfecha_por(candidato)


@dataclass(frozen=True)
class _No(Especificacion[T]):
    a: Especificacion

    def es_satisfecha_por(self, candidato):
        return not self.a.es_satisfecha_por(candidato)


# --------------------------------------------------------------------------
# Especificaciones sobre el agendado de una cita (US-04, US-05, US-10)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ContextoDeAgendado:
    cita: Cita
    fecha: date
    medico_id: str
    jornadas: tuple[Jornada, ...]
    citas_activas: tuple[Cita, ...]  # citas que bloquean franja, sin la que se coloca
    limite_sobrecupo: int


class CitaDelMedicoYFecha(Especificacion[ContextoDeAgendado]):
    def es_satisfecha_por(self, ctx):
        return ctx.cita.medico_id == ctx.medico_id and ctx.cita.franja.inicio.date() == ctx.fecha


class FranjaDentroDeJornadaVigente(Especificacion[ContextoDeAgendado]):
    """US-01/US-04: solo se agenda en una jornada vigente de esa sucursal."""

    def es_satisfecha_por(self, ctx):
        return any(
            j.sucursal_id == ctx.cita.sucursal_id and j.contiene(ctx.cita.franja)
            for j in ctx.jornadas
        )


def _ocupadas(ctx: ContextoDeAgendado) -> int:
    return sum(1 for c in ctx.citas_activas if c.franja.se_solapa(ctx.cita.franja))


class HorarioLibre(Especificacion[ContextoDeAgendado]):
    """US-05: ninguna cita activa del médico, en cualquier sucursal, ocupa la franja."""

    def es_satisfecha_por(self, ctx):
        return _ocupadas(ctx) == 0


class SobrecupoDisponible(Especificacion[ContextoDeAgendado]):
    """US-10: hay cita previa pero no se ha agotado el límite del médico."""

    def es_satisfecha_por(self, ctx):
        ocupadas = _ocupadas(ctx)
        return ocupadas >= 1 and ocupadas < 1 + ctx.limite_sobrecupo


# --------------------------------------------------------------------------
# Especificaciones de otros casos de uso
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PacienteSinCitaSolapada(Especificacion[FranjaHoraria]):
    """Q8 del levantamiento: un paciente no agenda dos citas simultáneas."""

    franjas_del_paciente: tuple[FranjaHoraria, ...]

    def es_satisfecha_por(self, franja):
        return not any(f.se_solapa(franja) for f in self.franjas_del_paciente)


@dataclass(frozen=True)
class JornadaSinTraslape(Especificacion[Jornada]):
    """Un médico no puede estar en dos sucursales a la vez."""

    jornadas: tuple[Jornada, ...]

    def es_satisfecha_por(self, jornada):
        return not any(
            not j.cancelada and j.franja.se_solapa(jornada.franja) for j in self.jornadas
        )


@dataclass(frozen=True)
class CitaEnEstado(Especificacion[Cita]):
    estados: tuple[EstadoCita, ...]

    def es_satisfecha_por(self, cita):
        return cita.estado in self.estados


@dataclass(frozen=True)
class HoraYaPaso(Especificacion[Cita]):
    """US-14/US-20: solo es no-show una cita cuya hora de inicio ya pasó."""

    ahora: datetime

    def es_satisfecha_por(self, cita):
        return self.ahora > cita.franja.inicio


@dataclass(frozen=True)
class LlegadaEnElDiaDeLaCita(Especificacion[Cita]):
    """US-07: la llegada se registra el día de la cita."""

    ahora: datetime

    def es_satisfecha_por(self, cita):
        return cita.franja.inicio.date() == self.ahora.date()


class RequiereAutorizacion(Especificacion):
    """US-12: la aseguradora exige autorización previa (dato del catálogo, P9)."""

    def es_satisfecha_por(self, aseguradora):
        return bool(aseguradora is not None and aseguradora.exige_autorizacion)


def todas(especificaciones: Iterable[Especificacion]) -> Especificacion:
    it = iter(especificaciones)
    resultado = next(it)
    for e in it:
        resultado = resultado & e
    return resultado
