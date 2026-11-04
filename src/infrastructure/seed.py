"""Datos de demostración (ficticios) para la defensa. Idempotente."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import select

from src.application.comandos import AbrirJornadaCommand, RegistrarPacienteCommand
from src.domain.value_objects import FranjaHoraria

from . import db


def cargar_demo(contenedor) -> bool:
    with contenedor.session_factory() as s:
        if s.scalar(select(db.SucursalRow.id).limit(1)):
            return False
    cat, jor, pac = contenedor.catalogo, contenedor.jornadas, contenedor.pacientes
    for i, n in (("CENTRO", "MediNova Centro"), ("NORTE", "MediNova Norte"), ("SUR", "MediNova Sur")):
        cat.crear_sucursal(i, n)
    for i, n in (("MG", "Medicina general"), ("CARD", "Cardiología"), ("PED", "Pediatría")):
        cat.crear_especialidad(i, n)
    cat.crear_aseguradora("ASEGURAMAX", "AseguraMax (solo póliza)", False, 0)
    cat.crear_aseguradora("SALUDPLUS", "SaludPlus (autorización escrita 48 h)", True, 48)
    cat.crear_medico("MED-001", "Dra. Ana Treviño", ("MG",), 0)
    cat.crear_medico("MED-002", "Dr. Luis Garza", ("CARD", "MG"), 2)  # acepta hasta 2 en sobrecupo
    cat.crear_medico("MED-003", "Dra. Marta Salinas", ("PED",), 1, por_honorarios=True)
    hoy = contenedor.reloj.ahora().date()
    for d in range(0, 4):
        dia = hoy + timedelta(days=d)
        def f(h1, h2, dia=dia):
            return FranjaHoraria(datetime.combine(dia, time(h1)), datetime.combine(dia, time(h2)))
        jor.abrir_jornada(AbrirJornadaCommand("MED-001", "CENTRO", f(9, 14)))
        jor.abrir_jornada(AbrirJornadaCommand("MED-002", "CENTRO", f(9, 12)))
        jor.abrir_jornada(AbrirJornadaCommand("MED-002", "NORTE", f(14, 18)))  # atiende en dos sucursales
        jor.abrir_jornada(AbrirJornadaCommand("MED-003", "SUR", f(10, 16)))
    pac.registrar_paciente(RegistrarPacienteCommand("Paciente Demo Uno", "8112345678", None, "demo1@example.com"))
    pac.registrar_paciente(RegistrarPacienteCommand("Paciente Demo Dos", "8187654321", None, "demo2@example.com",
                                                    "SALUDPLUS"))
    return True
