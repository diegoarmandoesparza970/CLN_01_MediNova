"""Unit of Work: una transacción por caso de uso (informe, sección 5; ADR-003).

Orden al confirmar: 1) se recogen los eventos de los agregados tocados, 2) la auditoría
se escribe antes de confirmar (misma transacción), 3) commit, 4) se notifica.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain import eventos as ev
from src.domain.repositorios import (
    AgendaMedicaRepository,
    AseguradoraRepository,
    EspecialidadRepository,
    MedicoRepository,
    PacienteRepository,
    RegistroDeAuditoriaRepository,
    SucursalRepository,
)

from .puertos import Mensaje, Notificador


class UnitOfWork(ABC):
    agendas: AgendaMedicaRepository
    pacientes: PacienteRepository
    medicos: MedicoRepository
    aseguradoras: AseguradoraRepository
    sucursales: SucursalRepository
    especialidades: EspecialidadRepository
    auditoria: RegistroDeAuditoriaRepository

    def __init__(self, notificador: Notificador | None = None):
        self.notificador = notificador
        self.vistos: list = []
        self.eventos_confirmados: list[ev.Evento] = []
        self._confirmada = False

    # --- contrato de infraestructura
    @abstractmethod
    def _abrir(self): ...
    @abstractmethod
    def _commit(self): ...
    @abstractmethod
    def _rollback(self): ...
    @abstractmethod
    def _cerrar(self): ...

    def __enter__(self):
        self._abrir()
        return self

    def __exit__(self, tipo, valor, tb):
        try:
            if tipo is not None or not self._confirmada:
                self._rollback()
        finally:
            self._cerrar()
        return False

    def confirmar(self):
        eventos: list[ev.Evento] = []
        for agregado in self.vistos:
            eventos.extend(agregado.recoger_eventos())
        for e in eventos:  # dentro de la transacción: sin cita cancelada sin su registro
            if isinstance(e, ev.EVENTOS_AUDITABLES):
                self.auditoria.agregar(ev.RegistroDeAuditoria(
                    e.cita_id, e.usuario, e.ocurrido_en, e.motivo, type(e).__name__))
        self._commit()
        self._confirmada = True
        self.eventos_confirmados = eventos
        self._notificar(eventos)

    def _notificar(self, eventos):
        """Después de confirmar; un fallo aquí nunca deshace la cita (informe, sección 5)."""
        if self.notificador is None:
            return
        for e in eventos:
            try:
                msg = self._mensaje_para(e)
                if msg:
                    self.notificador.enviar(msg)
            except Exception:  # noqa: BLE001 - la notificación queda para reintento manual
                continue

    def _mensaje_para(self, e: ev.Evento) -> Mensaje | None:
        if isinstance(e, ev.CitaAgendada):
            texto = f"MediNova: su cita fue agendada para {e.detalle['inicio']}."
            expediente, canal = e.detalle["expediente"], e.detalle["canal"]
        elif isinstance(e, ev.CitaCancelada):
            texto = f"MediNova: su cita fue cancelada. Motivo: {e.motivo}."
            expediente = self._expediente_de(e.cita_id)
            canal = self._canal_de(e.cita_id)
        elif isinstance(e, ev.CitaAfectadaPorJornada):
            texto = "MediNova: su médico canceló la jornada; recepción le llamará para reagendar."
            expediente = self._expediente_de(e.cita_id)
            canal = "telefono"
        else:
            return None
        paciente = self.pacientes.obtener_por_expediente(expediente) if expediente else None
        if paciente is None:
            return None
        return Mensaje(e.cita_id, expediente, paciente.contacto.telefono, canal, texto)

    def _expediente_de(self, cita_id):
        return self.agendas.obtener_por_cita(cita_id).obtener_cita(cita_id).expediente

    def _canal_de(self, cita_id):
        return self.agendas.obtener_por_cita(cita_id).obtener_cita(cita_id).canal
