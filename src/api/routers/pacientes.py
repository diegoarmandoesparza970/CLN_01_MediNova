from fastapi import APIRouter, Depends, Query

from src.api.dependencias import contenedor
from src.api.esquemas import ErrorOut, PacienteActualizarIn, PacienteIn, PacienteOut
from src.api.seguridad import CUALQUIER_ROL, SOLO_RECEPCION
from src.application.comandos import ActualizarPacienteCommand, RegistrarPacienteCommand
from src.domain.errores import DatosInvalidos

router = APIRouter(prefix="/pacientes", tags=["Pacientes"])


def _out(p) -> PacienteOut:
    return PacienteOut(expediente=p.expediente, nombre=p.nombre, telefono=p.contacto.telefono,
                       correo=p.contacto.correo, nacimiento=p.nacimiento, aseguradora_id=p.aseguradora_id)


@router.post("", response_model=PacienteOut, status_code=201, dependencies=[Depends(SOLO_RECEPCION)],
             responses={409: {"model": ErrorOut, "description": "Paciente duplicado (mismo teléfono)"}},
             summary="Registrar paciente nuevo con expediente único (US-02)")
def registrar(body: PacienteIn, c=Depends(contenedor)):
    exp = c.pacientes.registrar_paciente(RegistrarPacienteCommand(
        body.nombre, body.telefono, body.nacimiento, body.correo, body.aseguradora_id))
    return _out(c.pacientes.buscar(expediente=exp))


@router.get("", response_model=PacienteOut, dependencies=[Depends(CUALQUIER_ROL)],
            summary="Buscar por expediente o teléfono (US-03)")
def buscar(expediente: str | None = Query(None), telefono: str | None = Query(None), c=Depends(contenedor)):
    if not expediente and not telefono:
        raise DatosInvalidos("Indique expediente o telefono")
    return _out(c.pacientes.buscar(expediente, telefono))


@router.patch("/{expediente}", response_model=PacienteOut, dependencies=[Depends(SOLO_RECEPCION)],
              summary="Actualizar teléfono, correo o aseguradora (US-22)")
def actualizar(expediente: str, body: PacienteActualizarIn, c=Depends(contenedor)):
    return _out(c.pacientes.actualizar_paciente(ActualizarPacienteCommand(
        expediente, body.telefono, body.correo, body.aseguradora_id, body.actualiza_aseguradora)))
