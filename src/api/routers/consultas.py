from datetime import date

from fastapi import APIRouter, Depends, Query

from src.api.dependencias import contenedor
from src.api.esquemas import (
    AuditoriaOut,
    CitaAfectadaVMOut,
    DisponibilidadOut,
    ErrorOut,
    HistorialNoShowsOut,
    NotificacionOut,
    ReporteOut,
)
from src.api.seguridad import ANALISIS, CUALQUIER_ROL
from src.application import consultas as q
from src.domain.errores import DatosInvalidos, PacienteNoEncontrado

router = APIRouter(prefix="/consultas", tags=["Consultas (CQRS)"])


@router.get("/disponibilidad", response_model=list[DisponibilidadOut], dependencies=[Depends(CUALQUIER_ROL)],
            summary="Disponibilidad del médico en todas sus sucursales (US-01, US-16)")
def disponibilidad(fecha: date, medico_id: str | None = None, especialidad: str | None = None,
                   sucursal_id: str | None = None, solo_libres: bool = False, c=Depends(contenedor)):
    return c.consultas.disponibilidad(q.ConsultarDisponibilidadDelMedico(
        fecha, medico_id, especialidad, sucursal_id, solo_libres))


@router.get("/citas-afectadas", response_model=list[CitaAfectadaVMOut], dependencies=[Depends(CUALQUIER_ROL)],
            summary="Pacientes afectados por una jornada cancelada, la cita más próxima primero (US-11)")
def citas_afectadas(medico_id: str, fecha: date, sucursal_id: str | None = None, c=Depends(contenedor)):
    return c.consultas.citas_afectadas(q.ConsultarCitasAfectadas(medico_id, fecha, sucursal_id))


@router.get("/historial-no-shows/{expediente}", response_model=HistorialNoShowsOut,
            dependencies=[Depends(CUALQUIER_ROL)], responses={404: {"model": ErrorOut}},
            summary="Historial de no-shows de un paciente (US-14)")
def historial(expediente: str, c=Depends(contenedor)):
    vm = c.consultas.historial_no_shows(q.ConsultarHistorialDeNoShows(expediente))
    if vm is None:
        raise PacienteNoEncontrado(f"Paciente {expediente} no encontrado")
    return vm


@router.get("/reporte", response_model=ReporteOut, dependencies=[Depends(ANALISIS)],
            summary="Reporte consolidado por sucursal y médico (US-15, US-24)")
def reporte(desde: date, hasta: date, c=Depends(contenedor)):
    if hasta < desde:
        raise DatosInvalidos("'hasta' no puede ser anterior a 'desde'")
    return c.consultas.reporte(q.ObtenerReporteConsolidado(desde, hasta))


@router.get("/auditoria", response_model=list[AuditoriaOut], dependencies=[Depends(ANALISIS)],
            summary="Evidencia de cancelaciones y modificaciones (US-17)")
def auditoria(cita_id: str | None = Query(None), c=Depends(contenedor)):
    return c.consultas.auditoria(cita_id)


@router.get("/notificaciones", response_model=list[NotificacionOut], dependencies=[Depends(CUALQUIER_ROL)],
            summary="Bandeja de notificaciones por canal (US-18)")
def notificaciones(limite: int = Query(50, ge=1, le=500), c=Depends(contenedor)):
    return c.consultas.notificaciones(limite)
