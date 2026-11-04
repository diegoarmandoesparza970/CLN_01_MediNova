"""Repositorios SQL: traducen entre filas y objetos de dominio (el dominio no importa SQLAlchemy)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from src.domain.agenda_medica import AgendaMedica
from src.domain.catalogos import Aseguradora, Especialidad, Medico, Paciente, Sucursal
from src.domain.cita import Cita
from src.domain.errores import CitaNoEncontrada, ConflictoDeVersion
from src.domain.estados import EstadoCita
from src.domain.eventos import RegistroDeAuditoria
from src.domain.jornada import Jornada
from src.domain.repositorios import (
    AgendaMedicaRepository,
    AseguradoraRepository,
    EspecialidadRepository,
    MedicoRepository,
    PacienteRepository,
    RegistroDeAuditoriaRepository,
    SucursalRepository,
)
from src.domain.value_objects import (
    Autorizacion,
    CierreDeConsulta,
    Confirmacion,
    Contacto,
    EstadoAutorizacion,
    FranjaHoraria,
    LimiteDeSobrecupo,
    RespuestaDeConfirmacion,
)

from . import db

ESTADOS_BLOQUEANTES = [EstadoCita.AGENDADA.value, EstadoCita.PENDIENTE_AUTORIZACION.value,
                       EstadoCita.PRESENTE.value, EstadoCita.ATENDIDA.value]


# ------------------------------------------------------------------ mapeos
def _cita_a_dominio(r: db.CitaRow) -> Cita:
    aut = Autorizacion(EstadoAutorizacion(r.aut_estado), r.aut_numero) if r.aut_estado else None
    conf = (Confirmacion(r.conf_envio, r.conf_canal or "", RespuestaDeConfirmacion(r.conf_respuesta))
            if r.conf_envio else None)
    cierre = (CierreDeConsulta(r.cierre_receta or "", tuple(r.cierre_estudios or ()), bool(r.cierre_nueva_cita))
              if r.cierre_nueva_cita is not None else None)
    return Cita(r.id, r.expediente, r.medico_id, r.sucursal_id, FranjaHoraria(r.inicio, r.fin), r.especialidad,
                r.motivo, r.canal, r.aseguradora_id, aut, EstadoCita(r.estado), r.cita_origen_id, r.llegada,
                conf, cierre, r.creada_en, r.reagendada_en)


def _cita_a_fila(c: Cita, fecha: date) -> db.CitaRow:
    return db.CitaRow(
        id=c.id, medico_id=c.medico_id, fecha=fecha, expediente=c.expediente, sucursal_id=c.sucursal_id,
        inicio=c.franja.inicio, fin=c.franja.fin, especialidad=c.especialidad, motivo=c.motivo, canal=c.canal,
        aseguradora_id=c.aseguradora_id,
        aut_estado=c.autorizacion.estado.value if c.autorizacion else None,
        aut_numero=c.autorizacion.numero if c.autorizacion else None,
        estado=c.estado.value, cita_origen_id=c.cita_origen_id, llegada=c.llegada,
        conf_envio=c.confirmacion.fecha_envio if c.confirmacion else None,
        conf_canal=c.confirmacion.canal if c.confirmacion else None,
        conf_respuesta=c.confirmacion.respuesta.value if c.confirmacion else None,
        cierre_receta=c.cierre.receta if c.cierre else None,
        cierre_estudios=list(c.cierre.estudios) if c.cierre else None,
        cierre_nueva_cita=c.cierre.requiere_nueva_cita if c.cierre else None,
        creada_en=c.creada_en, reagendada_en=c.reagendada_en)


class AgendaMedicaSql(AgendaMedicaRepository):
    def __init__(self, session, vistos: list):
        self.s, self.vistos = session, vistos

    def obtener_por_medico_y_fecha(self, medico_id, fecha):
        fila = self.s.get(db.AgendaRow, (medico_id, fecha))
        if fila is None:
            return AgendaMedica(medico_id, fecha)
        jornadas = self.s.scalars(select(db.JornadaRow).where(
            db.JornadaRow.medico_id == medico_id, db.JornadaRow.fecha == fecha).order_by(db.JornadaRow.inicio))
        citas = self.s.scalars(select(db.CitaRow).where(
            db.CitaRow.medico_id == medico_id, db.CitaRow.fecha == fecha).order_by(db.CitaRow.inicio))
        return AgendaMedica(
            medico_id, fecha,
            [Jornada(j.id, j.sucursal_id, FranjaHoraria(j.inicio, j.fin), j.cancelada, j.cancelada_en)
             for j in jornadas],
            [_cita_a_dominio(c) for c in citas], fila.version)

    def obtener_por_cita(self, cita_id):
        fila = self.s.get(db.CitaRow, cita_id)
        if fila is None:
            raise CitaNoEncontrada(f"Cita {cita_id} no encontrada")
        return self.obtener_por_medico_y_fecha(fila.medico_id, fila.fecha)

    def guardar(self, agenda):
        if agenda.version == 0:
            try:
                self.s.add(db.AgendaRow(medico_id=agenda.medico_id, fecha=agenda.fecha, version=1))
                self.s.flush()
            except IntegrityError as ex:
                raise ConflictoDeVersion("La agenda fue creada por otra transacción") from ex
            nueva_version = 1
        else:
            res = self.s.execute(
                update(db.AgendaRow)
                .where(db.AgendaRow.medico_id == agenda.medico_id, db.AgendaRow.fecha == agenda.fecha,
                       db.AgendaRow.version == agenda.version)
                .values(version=agenda.version + 1))
            if res.rowcount == 0:
                raise ConflictoDeVersion("La agenda cambió desde que se leyó")
            nueva_version = agenda.version + 1
        # Jornadas y citas del Aggregate: se sincronizan completas
        ids_j = {j.id for j in agenda.jornadas}
        ids_c = {c.id for c in agenda.citas}
        self.s.execute(delete(db.JornadaRow).where(
            db.JornadaRow.medico_id == agenda.medico_id, db.JornadaRow.fecha == agenda.fecha,
            db.JornadaRow.id.not_in(ids_j or {""})))
        self.s.execute(delete(db.CitaRow).where(
            db.CitaRow.medico_id == agenda.medico_id, db.CitaRow.fecha == agenda.fecha,
            db.CitaRow.id.not_in(ids_c or {""})))
        for j in agenda.jornadas:
            self.s.merge(db.JornadaRow(id=j.id, medico_id=agenda.medico_id, fecha=agenda.fecha,
                                       sucursal_id=j.sucursal_id, inicio=j.franja.inicio, fin=j.franja.fin,
                                       cancelada=j.cancelada, cancelada_en=j.cancelada_en))
        for c in agenda.citas:
            self.s.merge(_cita_a_fila(c, agenda.fecha))
        self.s.flush()
        agenda.version = nueva_version
        self.vistos.append(agenda)

    def franjas_activas_de_paciente(self, expediente, fecha):
        filas = self.s.execute(select(db.CitaRow.inicio, db.CitaRow.fin).where(
            db.CitaRow.expediente == expediente, db.CitaRow.fecha == fecha,
            db.CitaRow.estado.in_(ESTADOS_BLOQUEANTES)))
        return [FranjaHoraria(i, f) for i, f in filas]

    def contar_no_shows(self, expediente):
        return self.s.scalar(select(func.count()).select_from(db.CitaRow).where(
            db.CitaRow.expediente == expediente, db.CitaRow.estado == EstadoCita.NO_SHOW.value)) or 0

    def listar_por_rango(self, desde, hasta):
        claves = self.s.execute(select(db.AgendaRow.medico_id, db.AgendaRow.fecha).where(
            db.AgendaRow.fecha >= desde, db.AgendaRow.fecha <= hasta).order_by(db.AgendaRow.fecha))
        return [self.obtener_por_medico_y_fecha(m, f) for m, f in claves.all()]


class PacienteSql(PacienteRepository):
    def __init__(self, session):
        self.s = session

    @staticmethod
    def _dominio(r):
        return Paciente(r.expediente, r.nombre, Contacto(r.telefono, r.correo), r.nacimiento, r.aseguradora_id)

    def obtener_por_expediente(self, numero):
        r = self.s.get(db.PacienteRow, numero)
        return self._dominio(r) if r else None

    def buscar_por_telefono(self, telefono):
        r = self.s.scalar(select(db.PacienteRow).where(db.PacienteRow.telefono_normalizado == telefono))
        return self._dominio(r) if r else None

    def agregar(self, p):
        self.s.add(db.PacienteRow(expediente=p.expediente, nombre=p.nombre, telefono=p.contacto.telefono,
                                  telefono_normalizado=p.contacto.telefono_normalizado, correo=p.contacto.correo,
                                  nacimiento=p.nacimiento, aseguradora_id=p.aseguradora_id))
        self.s.flush()

    def guardar(self, p):
        self.s.merge(db.PacienteRow(expediente=p.expediente, nombre=p.nombre, telefono=p.contacto.telefono,
                                    telefono_normalizado=p.contacto.telefono_normalizado, correo=p.contacto.correo,
                                    nacimiento=p.nacimiento, aseguradora_id=p.aseguradora_id))
        self.s.flush()

    def siguiente_numero_de_expediente(self):
        fila = self.s.get(db.SecuenciaRow, "expediente", with_for_update=True)
        if fila is None:
            fila = db.SecuenciaRow(nombre="expediente", valor=0)
            self.s.add(fila)
        fila.valor += 1
        self.s.flush()
        return f"EXP-{fila.valor:06d}"


class MedicoSql(MedicoRepository):
    def __init__(self, session):
        self.s = session

    @staticmethod
    def _dominio(r):
        return Medico(r.id, r.nombre, tuple(r.especialidades or ()), LimiteDeSobrecupo(r.limite_sobrecupo),
                      r.por_honorarios)

    def obtener(self, medico_id):
        r = self.s.get(db.MedicoRow, medico_id)
        return self._dominio(r) if r else None

    def guardar(self, m):
        self.s.merge(db.MedicoRow(id=m.id, nombre=m.nombre, especialidades=list(m.especialidades),
                                  limite_sobrecupo=m.limite_sobrecupo.valor, por_honorarios=m.por_honorarios))
        self.s.flush()

    def listar(self):
        return [self._dominio(r) for r in self.s.scalars(select(db.MedicoRow).order_by(db.MedicoRow.id))]


class AseguradoraSql(AseguradoraRepository):
    def __init__(self, session):
        self.s = session

    @staticmethod
    def _dominio(r):
        return Aseguradora(r.id, r.nombre, r.exige_autorizacion, r.anticipacion_horas)

    def obtener(self, aseguradora_id):
        r = self.s.get(db.AseguradoraRow, aseguradora_id)
        return self._dominio(r) if r else None

    def guardar(self, a):
        self.s.merge(db.AseguradoraRow(id=a.id, nombre=a.nombre, exige_autorizacion=a.exige_autorizacion,
                                       anticipacion_horas=a.anticipacion_horas))
        self.s.flush()

    def listar(self):
        return [self._dominio(r) for r in self.s.scalars(select(db.AseguradoraRow).order_by(db.AseguradoraRow.id))]


class SucursalSql(SucursalRepository):
    def __init__(self, session):
        self.s = session

    def obtener(self, sucursal_id):
        r = self.s.get(db.SucursalRow, sucursal_id)
        return Sucursal(r.id, r.nombre) if r else None

    def guardar(self, e):
        self.s.merge(db.SucursalRow(id=e.id, nombre=e.nombre))
        self.s.flush()

    def listar(self):
        return [Sucursal(r.id, r.nombre) for r in self.s.scalars(select(db.SucursalRow).order_by(db.SucursalRow.id))]


class EspecialidadSql(EspecialidadRepository):
    def __init__(self, session):
        self.s = session

    def obtener(self, especialidad_id):
        r = self.s.get(db.EspecialidadRow, especialidad_id)
        return Especialidad(r.id, r.nombre) if r else None

    def guardar(self, e):
        self.s.merge(db.EspecialidadRow(id=e.id, nombre=e.nombre))
        self.s.flush()

    def listar(self):
        return [Especialidad(r.id, r.nombre)
                for r in self.s.scalars(select(db.EspecialidadRow).order_by(db.EspecialidadRow.id))]


class AuditoriaSql(RegistroDeAuditoriaRepository):
    """Solo agrega (invariante del Aggregate RegistroDeAuditoria)."""

    def __init__(self, session):
        self.s = session

    def agregar(self, r: RegistroDeAuditoria):
        self.s.add(db.AuditoriaRow(cita_id=r.cita_id, tipo=r.tipo, usuario=r.usuario, fecha=r.fecha,
                                   motivo=r.motivo))
        self.s.flush()
