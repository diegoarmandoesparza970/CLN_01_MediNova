"""Entidades de catálogo y de apoyo: datos de referencia, sin Aggregate propio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .errores import DatosInvalidos
from .eventos import DatosDePacienteActualizados, Evento, PacienteRegistrado
from .value_objects import Contacto, LimiteDeSobrecupo


@dataclass(frozen=True)
class Sucursal:
    id: str
    nombre: str


@dataclass(frozen=True)
class Especialidad:
    id: str
    nombre: str


@dataclass(frozen=True)
class Aseguradora:
    id: str
    nombre: str
    exige_autorizacion: bool = False
    anticipacion_horas: int = 0  # P9: algunas piden autorización escrita con 48 h


@dataclass
class Medico:
    id: str
    nombre: str
    especialidades: tuple[str, ...] = ()
    limite_sobrecupo: LimiteDeSobrecupo = field(default_factory=LimiteDeSobrecupo)
    por_honorarios: bool = False

    def definir_sobrecupo(self, valor: int):
        self.limite_sobrecupo = LimiteDeSobrecupo(valor)


@dataclass
class Paciente:
    """Aggregate: identificado por su número de expediente (US-02, US-03)."""

    expediente: str
    nombre: str
    contacto: Contacto
    nacimiento: date | None = None
    aseguradora_id: str | None = None
    eventos: list[Evento] = field(default_factory=list, repr=False)

    @staticmethod
    def registrar(expediente, nombre, contacto, nacimiento=None, aseguradora_id=None):
        if not nombre or not nombre.strip():
            raise DatosInvalidos("El nombre es obligatorio")
        p = Paciente(expediente, nombre.strip(), contacto, nacimiento, aseguradora_id)
        p.eventos.append(PacienteRegistrado(detalle={"expediente": expediente}))
        return p

    def actualizar_datos(self, telefono: str | None = None, correo: str | None = None,
                         aseguradora_id: str | None = None, cambia_aseguradora: bool = False):
        """US-22: confirmar teléfono y aseguradora en cada visita."""
        if telefono is not None or correo is not None:
            self.contacto = Contacto(telefono if telefono is not None else self.contacto.telefono,
                                     correo if correo is not None else self.contacto.correo)
        if cambia_aseguradora:
            self.aseguradora_id = aseguradora_id
        self.eventos.append(DatosDePacienteActualizados(detalle={"expediente": self.expediente}))

    def recoger_eventos(self) -> list[Evento]:
        e, self.eventos = self.eventos, []
        return e
