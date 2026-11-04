from datetime import date

from fastapi import APIRouter, Depends

from src.api.dependencias import contenedor
from src.api.esquemas import (
    AgendarCitaIn,
    AutorizacionIn,
    CambioDeEstatusOut,
    CancelarIn,
    CierreIn,
    CitaAgendadaOut,
    CitaOut,
    CitaReagendadaOut,
    ConfirmacionIn,
    EnviarConfirmacionesIn,
    ErrorOut,
    LlegadaIn,
    ModificarIn,
    ReagendarIn,
    ResultadoDeLlegadaOut,
)
from src.api.seguridad import CUALQUIER_ROL, SOLO_RECEPCION, Identidad
from src.application import comandos as cmd
from src.application import consultas as q
from src.domain.errores import CitaNoEncontrada
from src.domain.value_objects import CierreDeConsulta

router = APIRouter(prefix="/citas", tags=["Citas"])
ERR = {404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 422: {"model": ErrorOut}, 403: {"model": ErrorOut}}


def _agendar_cmd(b: AgendarCitaIn, usuario: str) -> cmd.AgendarCitaCommand:
    return cmd.AgendarCitaCommand(b.medico_id, b.franja.a_dominio(), b.sucursal_id, b.expediente, b.especialidad,
                                  b.motivo, b.canal.value, b.aseguradora_id, b.numero_autorizacion, usuario)


@router.post("", response_model=CitaAgendadaOut, status_code=201, responses=ERR,
             summary="Agendar cita y bloquear el horario (CU-01, US-04, US-05, US-10, US-12, US-18)")
def agendar(body: AgendarCitaIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.agendamiento.agendar_cita(_agendar_cmd(body, ident.usuario))


@router.get("", response_model=list[CitaOut], dependencies=[Depends(CUALQUIER_ROL)], summary="Listar citas con filtros")
def listar(fecha: date | None = None, medico_id: str | None = None, expediente: str | None = None,
           estado: str | None = None, c=Depends(contenedor)):
    return c.consultas.citas(q.ConsultarCitas(fecha, medico_id, expediente, estado))


@router.get("/{cita_id}", response_model=CitaOut, dependencies=[Depends(CUALQUIER_ROL)], responses=ERR)
def obtener(cita_id: str, c=Depends(contenedor)):
    vm = c.consultas.cita(cita_id)
    if vm is None:
        raise CitaNoEncontrada(f"Cita {cita_id} no encontrada")
    return vm


@router.post("/{cita_id}/cancelar", response_model=CambioDeEstatusOut, responses=ERR,
             summary="Cancelar cita con usuario, fecha y motivo (CU-04, US-17, US-19)")
def cancelar(cita_id: str, body: CancelarIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.agendamiento.cancelar_cita(cmd.CancelarCitaCommand(cita_id, ident.usuario, body.motivo))


@router.post("/{cita_id}/modificar", response_model=CambioDeEstatusOut, responses=ERR,
             summary="Modificar horario o sucursal de la cita (CU-04, US-19)")
def modificar(cita_id: str, body: ModificarIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.agendamiento.modificar_cita(cmd.ModificarCitaCommand(
        cita_id, body.franja.a_dominio(), body.sucursal_id, ident.usuario, body.motivo))


@router.post("/{cita_id}/autorizacion", response_model=CambioDeEstatusOut, responses=ERR,
             summary="Registrar el número de autorización de la aseguradora (US-12)")
def autorizacion(cita_id: str, body: AutorizacionIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.agendamiento.registrar_autorizacion(cmd.RegistrarAutorizacionCommand(cita_id, body.numero, ident.usuario))


@router.post("/{cita_id}/pago-particular", response_model=CambioDeEstatusOut, responses=ERR,
             summary="Sin autorización, el paciente paga como particular")
def pago_particular(cita_id: str, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.agendamiento.pagar_como_particular(cmd.PagarComoParticularCommand(cita_id, ident.usuario))


@router.post("/{cita_id}/llegada", response_model=ResultadoDeLlegadaOut, responses=ERR,
             summary="Registrar llegada y evaluar el retraso con tolerancia de 15 min (CU-02, US-07, US-08, US-09)")
def llegada(cita_id: str, body: LlegadaIn | None = None, ident: Identidad = Depends(SOLO_RECEPCION),
            c=Depends(contenedor)):
    b = body or LlegadaIn()
    return c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(
        cita_id, ident.usuario, b.hora_llegada, b.telefono, b.aseguradora_id, b.actualiza_aseguradora))


@router.post("/{cita_id}/no-atendida-por-retraso", response_model=CambioDeEstatusOut, responses=ERR,
             summary="El médico no puede atender al paciente con retraso (US-09)")
def no_atendida(cita_id: str, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.atencion.marcar_no_atendida_por_retraso(cmd.MarcarNoAtendidaPorRetrasoCommand(cita_id, ident.usuario))


@router.post("/{cita_id}/no-show", response_model=CambioDeEstatusOut, responses=ERR,
             summary="Marcar no-show (CU-05, US-14, US-20)")
def no_show(cita_id: str, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.atencion.marcar_no_show(cmd.MarcarNoShowCommand(cita_id, ident.usuario))


@router.post("/{cita_id}/cierre", response_model=CambioDeEstatusOut, responses=ERR,
             summary="Cerrar la consulta: receta, estudios y/o nueva cita (US-13)")
def cierre(cita_id: str, body: CierreIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    nueva = _agendar_cmd(body.nueva_cita, ident.usuario) if body.nueva_cita else None
    return c.atencion.cerrar_consulta(cmd.CerrarConsultaCommand(
        cita_id, CierreDeConsulta(body.receta, tuple(body.estudios), body.requiere_nueva_cita), ident.usuario, nueva))


@router.post("/{cita_id}/confirmacion", response_model=dict, responses=ERR,
             summary="Registrar la respuesta del paciente a la confirmación (US-06)")
def respuesta_confirmacion(cita_id: str, body: ConfirmacionIn, ident: Identidad = Depends(SOLO_RECEPCION),
                           c=Depends(contenedor)):
    return c.confirmaciones.registrar_respuesta(cmd.RegistrarRespuestaDeConfirmacionCommand(
        cita_id, body.respuesta, ident.usuario))


@router.post("/{cita_id}/reagendar", response_model=CitaReagendadaOut, status_code=201, responses=ERR,
             summary="Reagendar una cita afectada o no atendida por retraso: crea una cita vinculada (US-09, US-11)")
def reagendar(cita_id: str, body: ReagendarIn, ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    return c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(
        cita_id, body.medico_id, body.franja.a_dominio(), body.sucursal_id, ident.usuario))


@router.post("/confirmaciones/enviar", response_model=list[dict], tags=["Confirmaciones"],
             summary="Enviar recordatorios de las citas de una fecha por su canal de origen (US-06, US-18)")
def enviar_confirmaciones(body: EnviarConfirmacionesIn, ident: Identidad = Depends(SOLO_RECEPCION),
                          c=Depends(contenedor)):
    return c.confirmaciones.enviar_confirmaciones(cmd.EnviarConfirmacionesCommand(body.fecha, ident.usuario))


@router.post("/confirmaciones/liberar-sin-respuesta", response_model=dict, tags=["Confirmaciones"],
             summary="Liberar horarios sin confirmación tras 24 h (US-21)")
def liberar(ident: Identidad = Depends(SOLO_RECEPCION), c=Depends(contenedor)):
    ids = c.confirmaciones.liberar_sin_confirmacion()
    return {"liberadas": ids, "total": len(ids)}
