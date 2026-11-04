from fastapi import APIRouter, Depends

from src.api.dependencias import contenedor
from src.api.esquemas import (
    AseguradoraIn,
    AseguradoraOut,
    EspecialidadIn,
    EspecialidadOut,
    MedicoIn,
    MedicoOut,
    SobrecupoIn,
    SucursalIn,
    SucursalOut,
)
from src.api.seguridad import CUALQUIER_ROL, GESTION

router = APIRouter(tags=["Catálogos"])


def _medico(m):
    return MedicoOut(id=m.id, nombre=m.nombre, especialidades=list(m.especialidades),
                     limite_sobrecupo=m.limite_sobrecupo.valor, por_honorarios=m.por_honorarios)


@router.get("/sucursales", response_model=list[SucursalOut], dependencies=[Depends(CUALQUIER_ROL)])
def listar_sucursales(c=Depends(contenedor)):
    return c.catalogo.listar("sucursales")


@router.post("/sucursales", response_model=SucursalOut, status_code=201, dependencies=[Depends(GESTION)])
def crear_sucursal(body: SucursalIn, c=Depends(contenedor)):
    return c.catalogo.crear_sucursal(body.id, body.nombre)


@router.get("/especialidades", response_model=list[EspecialidadOut], dependencies=[Depends(CUALQUIER_ROL)])
def listar_especialidades(c=Depends(contenedor)):
    return c.catalogo.listar("especialidades")


@router.post("/especialidades", response_model=EspecialidadOut, status_code=201, dependencies=[Depends(GESTION)])
def crear_especialidad(body: EspecialidadIn, c=Depends(contenedor)):
    return c.catalogo.crear_especialidad(body.id, body.nombre)


@router.get("/aseguradoras", response_model=list[AseguradoraOut], dependencies=[Depends(CUALQUIER_ROL)])
def listar_aseguradoras(c=Depends(contenedor)):
    return c.catalogo.listar("aseguradoras")


@router.post("/aseguradoras", response_model=AseguradoraOut, status_code=201, dependencies=[Depends(GESTION)])
def crear_aseguradora(body: AseguradoraIn, c=Depends(contenedor)):
    return c.catalogo.crear_aseguradora(body.id, body.nombre, body.exige_autorizacion, body.anticipacion_horas)


@router.get("/medicos", response_model=list[MedicoOut], dependencies=[Depends(CUALQUIER_ROL)])
def listar_medicos(c=Depends(contenedor)):
    return [_medico(m) for m in c.catalogo.listar("medicos")]


@router.post("/medicos", response_model=MedicoOut, status_code=201, dependencies=[Depends(GESTION)])
def crear_medico(body: MedicoIn, c=Depends(contenedor)):
    return _medico(c.catalogo.crear_medico(body.id, body.nombre, body.especialidades,
                                           body.limite_sobrecupo, body.por_honorarios))


@router.put("/medicos/{medico_id}/sobrecupo", response_model=MedicoOut, dependencies=[Depends(GESTION)],
            summary="Definir el límite de sobrecupo del médico (US-10)")
def definir_sobrecupo(medico_id: str, body: SobrecupoIn, c=Depends(contenedor)):
    return _medico(c.catalogo.definir_sobrecupo(medico_id, body.limite))
