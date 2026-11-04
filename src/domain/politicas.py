"""Políticas como estrategias (ADR-005, principio abierto/cerrado)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .catalogos import Aseguradora
from .especificaciones import RequiereAutorizacion


class PoliticaDeAutorizacion(ABC):
    @abstractmethod
    def requiere(self, aseguradora: Aseguradora | None) -> bool: ...


class AutorizacionPorCatalogo(PoliticaDeAutorizacion):
    """Apoyada en el catálogo de aseguradoras (P9); usa la Specification del dominio."""

    def requiere(self, aseguradora):
        return RequiereAutorizacion().es_satisfecha_por(aseguradora)


class PoliticaDeNoShow(ABC):
    """Devuelve una advertencia para recepción o None si no hay nada que hacer."""

    @abstractmethod
    def evaluar(self, total_no_shows: int) -> str | None: ...


class SinSancionPorNoShow(PoliticaDeNoShow):
    def evaluar(self, total_no_shows):
        return None


class AlertaPorUmbralDeNoShows(PoliticaDeNoShow):
    """Decisión del equipo (pendiente de aprobación de dirección, P10): al llegar al
    umbral se alerta a recepción para reforzar la confirmación. No bloquea al paciente."""

    def __init__(self, umbral: int = 3):
        self.umbral = umbral

    def evaluar(self, total_no_shows):
        if total_no_shows >= self.umbral:
            return (f"Paciente con {total_no_shows} no-shows (umbral {self.umbral}): "
                    "confirmar la cita por teléfono 24 h antes")
        return None
