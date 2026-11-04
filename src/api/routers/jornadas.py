from fastapi import APIRouter, Depends

from src.api.dependencias import contenedor
from src.api.esquemas import CancelarJornadaIn, CitaAfectadaOut, ErrorOut, JornadaIn, JornadaOut
from src.api.seguridad import GESTION, SOLO_RECEPCION, Identidad
from src.application import comandos as cmd

router = APIRouter(prefix="/jornadas", tags=["Jornadas"])
ERR = {404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 422: {"model": ErrorOut}}


@router.post("", response_model=JornadaOut, status_code=201, dependencies=[Depends(GESTION)], responses=ERR,
             summary="Abrir la jornada del médico en una sucursal (horarios semanales)")
def abrir(body: JornadaIn, c=Depends(contenedor)):
    return JornadaOut(jornada_id=c.jornadas.abrir_jornada(
        cmd.AbrirJornadaCommand(body.medico_id, body.sucursal_id, body.franja.a_dominio())))


@router.post("/cancelar", response_model=list[CitaAfectadaOut], responses=ERR,
             summary="El médico cancela su jornada: las citas quedan afectadas (CU-03, US-11)")
def cancelar(body: CancelarJornadaIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.jornadas.cancelar_jornada(cmd.CancelarJornadaCommand(
        body.medico_id, body.fecha, ident.usuario, body.motivo, body.sucursal_id))
