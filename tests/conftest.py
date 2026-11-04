from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.composicion import construir
from src.api.main import crear_app
from src.application.comandos import AbrirJornadaCommand, AgendarCitaCommand, RegistrarPacienteCommand
from src.domain.value_objects import FranjaHoraria
from src.infrastructure import db
from src.infrastructure.config import Configuracion, normalizar_url_db
from src.infrastructure.reloj import RelojFijo

HOY = date(2026, 11, 10)
AHORA = datetime(2026, 11, 10, 8, 0)


def dt(h, m=0, dia=HOY):
    return datetime.combine(dia, time(h, m))


def franja(h, m=0, dur=30, dia=HOY):
    return FranjaHoraria(dt(h, m, dia), dt(h, m, dia) + timedelta(minutes=dur))


class Mundo:
    """Escenario de prueba: 2 sucursales, 3 médicos, 2 aseguradoras y 3 pacientes."""

    def __init__(self, contenedor, reloj):
        self.c, self.reloj = contenedor, reloj
        cat, jor, pac = contenedor.catalogo, contenedor.jornadas, contenedor.pacientes
        cat.crear_sucursal("A", "Sucursal A")
        cat.crear_sucursal("B", "Sucursal B")
        cat.crear_especialidad("MG", "Medicina general")
        cat.crear_especialidad("CARD", "Cardiología")
        cat.crear_aseguradora("PARTICULAR-POLIZA", "Solo póliza", False, 0)
        cat.crear_aseguradora("ASEG-AUT", "Pide autorización", True, 48)
        cat.crear_medico("M1", "Dr. Uno", ("MG",), 0)
        cat.crear_medico("M2", "Dra. Dos", ("MG", "CARD"), 2)
        cat.crear_medico("M3", "Dr. Tres", ("MG",), 0)
        for dia in (HOY, HOY + timedelta(days=1)):
            jor.abrir_jornada(AbrirJornadaCommand("M1", "A", franja(9, dur=240, dia=dia)))   # 9-13 en A
            jor.abrir_jornada(AbrirJornadaCommand("M1", "B", franja(14, dur=180, dia=dia)))  # 14-17 en B
            jor.abrir_jornada(AbrirJornadaCommand("M2", "A", franja(9, dur=240, dia=dia)))
            jor.abrir_jornada(AbrirJornadaCommand("M3", "B", franja(9, dur=240, dia=dia)))
        self.p1 = pac.registrar_paciente(RegistrarPacienteCommand("Ana Pérez", "8110000001", correo="ana@example.com"))
        self.p2 = pac.registrar_paciente(RegistrarPacienteCommand("Beto Ruiz", "8110000002"))
        self.p3 = pac.registrar_paciente(RegistrarPacienteCommand("Carla Soto", "8110000003", aseguradora_id="ASEG-AUT"))

    def agendar(self, medico="M1", sucursal="A", h=9, m=0, expediente=None, dia=HOY, **kw):
        cmd = AgendarCitaCommand(medico, franja(h, m, dia=dia), sucursal, expediente or self.p1,
                                 kw.pop("especialidad", "MG"), kw.pop("motivo", "consulta"), **kw)
        return self.c.agendamiento.agendar_cita(cmd)


@pytest.fixture
def engine():
    url = normalizar_url_db(os.environ.get("TEST_DATABASE_URL", "sqlite://"))
    eng = db.crear_engine(url)
    db.borrar_esquema(eng)
    db.crear_esquema(eng)
    yield eng
    db.borrar_esquema(eng)
    eng.dispose()


@pytest.fixture
def reloj():
    return RelojFijo(AHORA)


@pytest.fixture
def contenedor(engine, reloj):
    return construir(Configuracion(database_url="sqlite://"), reloj=reloj, engine=engine)


@pytest.fixture
def mundo(contenedor, reloj):
    return Mundo(contenedor, reloj)


@pytest.fixture
def client(contenedor, mundo):
    app = crear_app(Configuracion(database_url="sqlite://"), contenedor=contenedor)
    with TestClient(app) as c:
        yield c


RECEPCION = {"X-Usuario": "maria", "X-Rol": "recepcion"}
ADMIN = {"X-Usuario": "luis", "X-Rol": "administrativo"}
DIRECCION = {"X-Usuario": "dir", "X-Rol": "direccion"}
