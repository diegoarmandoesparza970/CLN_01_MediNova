from __future__ import annotations

from src.application.puertos import Notificador
from src.application.unit_of_work import UnitOfWork

from . import repositorios_sql as r


class UnitOfWorkSql(UnitOfWork):
    """Una sesión SQLAlchemy = una transacción por caso de uso."""

    def __init__(self, session_factory, notificador: Notificador | None = None):
        super().__init__(notificador)
        self.session_factory = session_factory
        self.session = None

    def _abrir(self):
        self.session = self.session_factory()
        s = self.session
        self.agendas = r.AgendaMedicaSql(s, self.vistos)
        self.pacientes = r.PacienteSql(s)
        self.medicos = r.MedicoSql(s)
        self.aseguradoras = r.AseguradoraSql(s)
        self.sucursales = r.SucursalSql(s)
        self.especialidades = r.EspecialidadSql(s)
        self.auditoria = r.AuditoriaSql(s)

    def _commit(self):
        self.session.commit()

    def _rollback(self):
        self.session.rollback()

    def _cerrar(self):
        self.session.close()
