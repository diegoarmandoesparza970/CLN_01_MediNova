"""Composition root: único lugar donde se conectan puertos con adaptadores."""
from __future__ import annotations

from dataclasses import dataclass

from src.application.agendamiento_service import AgendamientoService
from src.application.atencion_service import AtencionService
from src.application.catalogo_service import CatalogoService
from src.application.confirmacion_service import ConfirmacionService
from src.application.consulta_service import ConsultaService
from src.application.jornada_service import JornadaService
from src.application.paciente_service import PacienteService
from src.domain.politicas import AlertaPorUmbralDeNoShows, AutorizacionPorCatalogo
from src.domain.reagendador import Reagendador
from src.domain.value_objects import Tolerancia
from src.infrastructure import db
from src.infrastructure.config import Configuracion
from src.infrastructure.lectores_sql import LectorSql
from src.infrastructure.notificador import NotificadorPorCanal
from src.infrastructure.reloj import RelojDelSistema, RelojSimulable
from src.infrastructure.unit_of_work_sql import UnitOfWorkSql


@dataclass
class Contenedor:
    config: Configuracion
    engine: object
    session_factory: object
    reloj: object
    agendamiento: AgendamientoService
    atencion: AtencionService
    jornadas: JornadaService
    pacientes: PacienteService
    catalogo: CatalogoService
    confirmaciones: ConfirmacionService
    consultas: ConsultaService


def construir(config: Configuracion, reloj=None, engine=None) -> Contenedor:
    engine = engine or db.crear_engine(config.database_url)
    sf = db.crear_session_factory(engine)
    reloj = reloj or RelojDelSistema(config.zona_horaria)
    if config.reloj_simulable:
        reloj = RelojSimulable(reloj)
    notificador = NotificadorPorCanal(sf, reloj, config.whatsapp_modo)

    def uow_factory():
        return UnitOfWorkSql(sf, notificador)

    pol_aut = AutorizacionPorCatalogo()
    pol_ns = AlertaPorUmbralDeNoShows(config.noshow_umbral)
    agend = AgendamientoService(uow_factory, pol_aut, pol_ns, reloj)
    return Contenedor(
        config, engine, sf, reloj, agend,
        AtencionService(uow_factory, reloj, Tolerancia(config.tolerancia_minutos), pol_ns, agend),
        JornadaService(uow_factory, reloj, Reagendador()),
        PacienteService(uow_factory), CatalogoService(uow_factory),
        ConfirmacionService(uow_factory, reloj, notificador, config.confirmacion_limite_horas),
        ConsultaService(LectorSql(sf, config.duracion_cita_minutos), pol_ns))
