"""Lectores de consulta (CQRS, ADR-004): leen directo de la BD y arman View Models.
No contienen reglas de negocio ni cargan Aggregates."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from src.application import consultas as q
from src.application.lectores import LectorDeConsultas
from src.domain.estados import EstadoCita

from . import db

BLOQUEANTES = {EstadoCita.AGENDADA.value, EstadoCita.PENDIENTE_AUTORIZACION.value,
               EstadoCita.PRESENTE.value, EstadoCita.ATENDIDA.value}


class LectorSql(LectorDeConsultas):
    def __init__(self, session_factory, duracion_cita_min: int = 30):
        self.sf = session_factory
        self.duracion = duracion_cita_min

    # -------------------------------------------------- US-01 / US-16
    def disponibilidad(self, c):
        with self.sf() as s:
            medicos = s.scalars(select(db.MedicoRow).order_by(db.MedicoRow.id)).all()
            if c.medico_id:
                medicos = [m for m in medicos if m.id == c.medico_id]
            if c.especialidad:
                medicos = [m for m in medicos if c.especialidad in (m.especialidades or [])]
            resultado = []
            for m in medicos:
                jornadas = s.scalars(select(db.JornadaRow).where(
                    db.JornadaRow.medico_id == m.id, db.JornadaRow.fecha == c.fecha,
                    db.JornadaRow.cancelada.is_(False)).order_by(db.JornadaRow.inicio)).all()
                citas = s.scalars(select(db.CitaRow).where(
                    db.CitaRow.medico_id == m.id, db.CitaRow.fecha == c.fecha,
                    db.CitaRow.estado.in_(BLOQUEANTES))).all()
                vm = q.DisponibilidadDelMedicoVM(m.id, m.nombre, list(m.especialidades or []), c.fecha)
                por_sucursal: dict[str, q.DisponibilidadSucursalVM] = {}
                for j in jornadas:
                    if c.sucursal_id and j.sucursal_id != c.sucursal_id:
                        continue
                    destino = por_sucursal.setdefault(j.sucursal_id, q.DisponibilidadSucursalVM(j.sucursal_id))
                    t = j.inicio
                    while t + timedelta(minutes=self.duracion) <= j.fin:
                        fin = t + timedelta(minutes=self.duracion)
                        ocupadas = sum(1 for x in citas if x.inicio < fin and t < x.fin)
                        if ocupadas == 0:
                            estado = "libre"
                        elif ocupadas < 1 + m.limite_sobrecupo:
                            estado = "sobrecupo_disponible"
                        else:
                            estado = "ocupada"
                        if not c.solo_libres or estado == "libre":
                            destino.franjas.append(q.FranjaVM(t, fin, estado))
                        t = fin
                vm.sucursales = list(por_sucursal.values())
                resultado.append(vm)
            return resultado

    # ------------------------------------------------------- US-11
    def citas_afectadas(self, c):
        with self.sf() as s:
            canceladas = s.scalars(select(db.JornadaRow).where(
                db.JornadaRow.medico_id == c.medico_id, db.JornadaRow.fecha == c.fecha,
                db.JornadaRow.cancelada.is_(True))).all()
            sucursales = {j.sucursal_id for j in canceladas if not c.sucursal_id or j.sucursal_id == c.sucursal_id}
            if not sucursales:
                return []
            citas = s.scalars(select(db.CitaRow).where(
                db.CitaRow.medico_id == c.medico_id, db.CitaRow.fecha == c.fecha,
                db.CitaRow.sucursal_id.in_(sucursales)).order_by(db.CitaRow.inicio)).all()
            afectadas_ids = set(s.scalars(select(db.AuditoriaRow.cita_id).where(
                db.AuditoriaRow.tipo == "CitaAfectadaPorJornada")).all())
            salida = []
            for ct in citas:
                if ct.id not in afectadas_ids:
                    continue
                p = s.get(db.PacienteRow, ct.expediente)
                nueva = s.scalar(select(db.CitaRow.id).where(db.CitaRow.cita_origen_id == ct.id))
                estado = {"afectada": "pendiente", "reagendada": "reagendada"}.get(ct.estado, ct.estado)
                salida.append(q.CitaAfectadaVM(ct.id, ct.expediente, p.nombre if p else "", p.telefono if p else "",
                                               p.correo if p else "", ct.inicio, estado, nueva))
            return salida

    # ------------------------------------------------------- US-14
    def historial_no_shows(self, c):
        with self.sf() as s:
            p = s.get(db.PacienteRow, c.expediente)
            if p is None:
                return None
            fechas = s.scalars(select(db.CitaRow.inicio).where(
                db.CitaRow.expediente == c.expediente,
                db.CitaRow.estado == EstadoCita.NO_SHOW.value).order_by(db.CitaRow.inicio)).all()
            return q.HistorialNoShowsVM(p.expediente, p.nombre, len(fechas), list(fechas))

    # ----------------------------------------------- US-15 / US-24
    def reporte(self, c):
        with self.sf() as s:
            citas = s.scalars(select(db.CitaRow).where(
                db.CitaRow.fecha >= c.desde, db.CitaRow.fecha <= c.hasta)).all()
            jornadas = s.scalars(select(db.JornadaRow).where(
                db.JornadaRow.fecha >= c.desde, db.JornadaRow.fecha <= c.hasta,
                db.JornadaRow.cancelada.is_(False))).all()
            medicos = {m.id: m.nombre for m in s.scalars(select(db.MedicoRow))}
            claves = {(x.sucursal_id, x.medico_id) for x in citas} | {(j.sucursal_id, j.medico_id) for j in jornadas}
            filas = []
            for suc, med in sorted(claves):
                cs = [x for x in citas if x.sucursal_id == suc and x.medico_id == med]
                minutos_jor = sum((j.fin - j.inicio).total_seconds() / 60 for j in jornadas
                                  if j.sucursal_id == suc and j.medico_id == med)
                minutos_ocup = sum((x.fin - x.inicio).total_seconds() / 60 for x in cs if x.estado in BLOQUEANTES)
                filas.append(q.FilaReporteVM(
                    suc, med, medicos.get(med, med), len(cs),
                    sum(1 for x in cs if x.estado == "atendida"),
                    sum(1 for x in cs if x.estado == "no_show"),
                    sum(1 for x in cs if x.estado == "cancelada"),
                    round(100 * minutos_ocup / minutos_jor, 1) if minutos_jor else 0.0))
            total = len(citas)
            no_shows = sum(1 for x in citas if x.estado == "no_show")
            # US-24: tiempo entre cancelar la jornada y reagendar al paciente
            tiempos = []
            canceladas = s.scalars(select(db.JornadaRow).where(
                db.JornadaRow.cancelada.is_(True), db.JornadaRow.cancelada_en.is_not(None))).all()
            for x in citas:
                if x.estado == "reagendada" and x.reagendada_en:
                    for j in canceladas:
                        if (j.medico_id, j.fecha, j.sucursal_id) == (x.medico_id, x.fecha, x.sucursal_id):
                            tiempos.append((x.reagendada_en - j.cancelada_en).total_seconds() / 60)
                            break
            promedio = round(sum(tiempos) / len(tiempos), 1) if tiempos else None
            return q.ReporteConsolidadoVM(c.desde, c.hasta, filas, total, no_shows,
                                          round(100 * no_shows / total, 1) if total else 0.0, promedio)

    # ------------------------------------------------- consultas de citas
    def _vm(self, s, x):
        p = s.get(db.PacienteRow, x.expediente)
        conf = x.conf_respuesta if x.conf_envio else None
        return q.CitaVM(x.id, x.expediente, p.nombre if p else "", x.medico_id, x.sucursal_id, x.inicio, x.fin,
                        x.estado, x.canal, x.especialidad, x.motivo, x.aseguradora_id, x.aut_estado, x.aut_numero,
                        conf, x.cita_origen_id, x.llegada)

    def citas(self, c):
        with self.sf() as s:
            stmt = select(db.CitaRow).order_by(db.CitaRow.inicio)
            if c.fecha:
                stmt = stmt.where(db.CitaRow.fecha == c.fecha)
            if c.medico_id:
                stmt = stmt.where(db.CitaRow.medico_id == c.medico_id)
            if c.expediente:
                stmt = stmt.where(db.CitaRow.expediente == c.expediente)
            if c.estado:
                stmt = stmt.where(db.CitaRow.estado == c.estado)
            return [self._vm(s, x) for x in s.scalars(stmt.limit(500))]

    def cita(self, cita_id):
        with self.sf() as s:
            x = s.get(db.CitaRow, cita_id)
            return self._vm(s, x) if x else None

    # -------------------------------------------------------- US-17
    def auditoria(self, cita_id):
        with self.sf() as s:
            stmt = select(db.AuditoriaRow).order_by(db.AuditoriaRow.id)
            if cita_id:
                stmt = stmt.where(db.AuditoriaRow.cita_id == cita_id)
            return [q.RegistroAuditoriaVM(a.cita_id, a.tipo, a.usuario, a.fecha, a.motivo)
                    for a in s.scalars(stmt.limit(1000))]

    def notificaciones(self, limite):
        with self.sf() as s:
            filas = s.scalars(select(db.NotificacionRow).order_by(db.NotificacionRow.id.desc()).limit(limite))
            return [q.NotificacionVM(n.id, n.cita_id, n.expediente, n.canal, n.estado, n.texto, n.creada_en)
                    for n in filas]
