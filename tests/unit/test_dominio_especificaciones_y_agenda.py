from datetime import timedelta

import pytest

from src.domain.agenda_medica import AgendaMedica
from src.domain.cita import Cita
from src.domain.errores import (CitaNoEncontrada, DatosInvalidos, FranjaFueraDeJornada, HorarioNoDisponible,
                                JornadaTraslapada, SobrecupoExcedido, TransicionDeEstatusInvalida)
from src.domain.especificaciones import (CitaEnEstado, HoraYaPaso, JornadaSinTraslape,
                                         PacienteSinCitaSolapada, RequiereAutorizacion, todas)
from src.domain.catalogos import Aseguradora
from src.domain.estados import EstadoCita
from src.domain import eventos as ev
from src.domain.jornada import Jornada
from src.domain.reagendador import Reagendador
from src.domain.value_objects import (Autorizacion, CierreDeConsulta, EstadoAutorizacion, MotivoDeCambio,
                                      RespuestaDeConfirmacion, ResultadoDeLlegada, Tolerancia)
from tests.conftest import AHORA, HOY, dt, franja

MOT = MotivoDeCambio("prueba")


def agenda(*, jornadas=((("A", 9, 13),)), medico="M1"):
    a = AgendaMedica(medico, HOY)
    for i, (s, h1, h2) in enumerate(jornadas):
        a.abrir_jornada(Jornada(f"J{i}", s, franja(h1, dur=(h2 - h1) * 60)))
    return a


def cita(id="C1", sucursal="A", h=9, m=0, exp="E1", medico="M1", **kw):
    return Cita(id, exp, medico, sucursal, franja(h, m), **kw)


# ------------------------------------------------------------------ Specification
def test_especificaciones_se_componen_con_y_o_no():
    c = cita()
    agendada = CitaEnEstado((EstadoCita.AGENDADA,))
    atendida = CitaEnEstado((EstadoCita.ATENDIDA,))
    assert (agendada | atendida).es_satisfecha_por(c)
    assert not (agendada & atendida).es_satisfecha_por(c)
    assert (~atendida).es_satisfecha_por(c)
    assert todas([agendada, ~atendida]).es_satisfecha_por(c)


@pytest.mark.traza("US-12")
def test_especificacion_requiere_autorizacion():
    assert RequiereAutorizacion().es_satisfecha_por(Aseguradora("X", "x", True))
    assert not RequiereAutorizacion().es_satisfecha_por(Aseguradora("X", "x", False))
    assert not RequiereAutorizacion().es_satisfecha_por(None)


def test_paciente_sin_cita_solapada_y_jornada_sin_traslape():
    assert not PacienteSinCitaSolapada((franja(9),)).es_satisfecha_por(franja(9, 15))
    assert PacienteSinCitaSolapada((franja(9),)).es_satisfecha_por(franja(9, 30))
    j = Jornada("J", "A", franja(9, dur=60))
    assert not JornadaSinTraslape((j,)).es_satisfecha_por(Jornada("K", "B", franja(9, 30, 60)))
    j.cancelada = True
    assert JornadaSinTraslape((j,)).es_satisfecha_por(Jornada("K", "B", franja(9, 30, 60)))


def test_hora_ya_paso():
    assert HoraYaPaso(dt(9, 1)).es_satisfecha_por(cita())
    assert not HoraYaPaso(dt(9)).es_satisfecha_por(cita())


# --------------------------------------------------------------- Aggregate: agendar
@pytest.mark.traza("US-04", "US-05", "CU-01", "ADR-002")
def test_T1_horario_ocupado_se_rechaza_en_cualquier_sucursal():
    a = agenda(jornadas=(("A", 9, 13),))
    a.jornadas.append(Jornada("JB", "B", franja(9, dur=240)))  # misma hora, otra sucursal (dato forzado)
    a.agendar(cita("C1", "A"), 0, AHORA)
    with pytest.raises(HorarioNoDisponible):
        a.agendar(cita("C2", "B", exp="E2"), 0, AHORA)
    assert len(a.citas) == 1


@pytest.mark.traza("US-10", "CU-01")
def test_T2_sobrecupo_dentro_y_por_encima_del_limite():
    a = agenda()
    a.agendar(cita("C1"), 2, AHORA)
    a.agendar(cita("C2", exp="E2"), 2, AHORA)   # 1.er sobrecupo
    a.agendar(cita("C3", exp="E3"), 2, AHORA)   # 2.º sobrecupo
    with pytest.raises(SobrecupoExcedido):
        a.agendar(cita("C4", exp="E4"), 2, AHORA)
    assert len(a.citas) == 3


@pytest.mark.traza("US-04")
def test_agendar_fuera_de_jornada_o_con_medico_distinto():
    a = agenda()
    with pytest.raises(FranjaFueraDeJornada):
        a.agendar(cita(h=14), 0, AHORA)                    # fuera de horario
    with pytest.raises(FranjaFueraDeJornada):
        a.agendar(cita(sucursal="B"), 0, AHORA)            # jornada de otra sucursal
    with pytest.raises(FranjaFueraDeJornada):
        a.agendar(cita(medico="OTRO"), 0, AHORA)
    a.agendar(cita("C1"), 0, AHORA)
    with pytest.raises(HorarioNoDisponible):
        a.agendar(cita("C1", h=10), 0, AHORA)               # id repetido


def test_cita_cancelada_libera_la_franja():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    a.cancelar("C1", "maria", MOT, AHORA)
    a.agendar(cita("C2", exp="E2"), 0, AHORA)
    assert isinstance(a.recoger_eventos()[1], ev.CitaCancelada)


def test_jornadas_de_un_medico_no_se_traslapan_ni_salen_de_la_fecha():
    a = agenda(jornadas=(("A", 9, 13),))
    with pytest.raises(JornadaTraslapada):
        a.abrir_jornada(Jornada("X", "B", franja(12, dur=120)))
    with pytest.raises(DatosInvalidos):
        a.abrir_jornada(Jornada("Y", "B", franja(23, dur=120)))
    a.abrir_jornada(Jornada("Z", "B", franja(14, dur=60)))   # médico en dos sucursales, sin traslape


# ----------------------------------------------------------- cancelar / modificar
@pytest.mark.traza("US-17", "US-19", "CU-04")
def test_modificar_cambia_franja_y_emite_evento_de_modificacion():
    a = agenda(jornadas=(("A", 9, 13), ("B", 14, 17)))
    a.agendar(cita("C1"), 0, AHORA)
    a.modificar("C1", franja(14), "B", 0, "maria", MOT, AHORA)
    c = a.obtener_cita("C1")
    assert c.sucursal_id == "B" and c.franja.inicio == dt(14)
    assert isinstance(a.recoger_eventos()[-1], ev.CitaModificada)


@pytest.mark.traza("US-19", "CU-04")
def test_modificar_a_horario_ocupado_no_cambia_nada():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    a.agendar(cita("C2", h=10, exp="E2"), 0, AHORA)
    with pytest.raises(HorarioNoDisponible):
        a.modificar("C2", franja(9), "A", 0, "maria", MOT, AHORA)
    assert a.obtener_cita("C2").franja.inicio == dt(10)


def test_modificar_puede_reutilizar_su_propia_franja_y_solo_si_esta_agendada():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    a.modificar("C1", franja(9, 15), "A", 0, "maria", MOT, AHORA)  # se solapa consigo misma: permitido
    a.cancelar("C1", "maria", MOT, AHORA)
    with pytest.raises(TransicionDeEstatusInvalida):
        a.modificar("C1", franja(10), "A", 0, "maria", MOT, AHORA)


def test_cita_inexistente():
    with pytest.raises(CitaNoEncontrada):
        agenda().obtener_cita("nada")


# -------------------------------------------------------------------- llegada
@pytest.mark.traza("US-07", "US-08", "US-09", "CU-02", "ADR-001")
@pytest.mark.parametrize("retraso,resultado,estado", [
    (0, ResultadoDeLlegada.A_TIEMPO, EstadoCita.PRESENTE),
    (14, ResultadoDeLlegada.CONSULTAR_MEDICO, EstadoCita.PRESENTE),
    (15, ResultadoDeLlegada.CONSULTAR_MEDICO, EstadoCita.PRESENTE),
    (16, ResultadoDeLlegada.NO_ATENDIDA_POR_RETRASO, EstadoCita.NO_ATENDIDA_POR_RETRASO)])
def test_T3_llegada_con_14_15_y_16_minutos(retraso, resultado, estado):
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    ahora = dt(9) + timedelta(minutes=retraso)
    assert a.registrar_llegada("C1", ahora, Tolerancia()) == resultado
    c = a.obtener_cita("C1")
    assert c.estado == estado
    assert (c.llegada == ahora) == (estado == EstadoCita.PRESENTE)


@pytest.mark.traza("US-07")
def test_llegada_solo_el_dia_de_la_cita_y_una_vez():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    with pytest.raises(TransicionDeEstatusInvalida):
        a.registrar_llegada("C1", dt(9) + timedelta(days=1), Tolerancia())
    a.registrar_llegada("C1", dt(9), Tolerancia())
    with pytest.raises(TransicionDeEstatusInvalida):
        a.registrar_llegada("C1", dt(9), Tolerancia())


@pytest.mark.traza("US-12")
def test_llegada_con_autorizacion_pendiente_se_bloquea_hasta_resolver():
    a = agenda()
    a.agendar(cita("C1", estado=EstadoCita.PENDIENTE_AUTORIZACION,
                   autorizacion=Autorizacion(EstadoAutorizacion.PENDIENTE)), 0, AHORA)
    with pytest.raises(TransicionDeEstatusInvalida):
        a.registrar_llegada("C1", dt(9), Tolerancia())
    a.registrar_autorizacion("C1", "AUT-1", "maria", AHORA)
    assert a.obtener_cita("C1").estado == EstadoCita.AGENDADA
    assert a.obtener_cita("C1").autorizacion.numero == "AUT-1"
    with pytest.raises(DatosInvalidos):
        a.registrar_autorizacion("C1", " ", "maria", AHORA)


def test_pagar_como_particular_quita_la_aseguradora():
    a = agenda()
    a.agendar(cita("C1", estado=EstadoCita.PENDIENTE_AUTORIZACION, aseguradora_id="X",
                   autorizacion=Autorizacion(EstadoAutorizacion.PENDIENTE)), 0, AHORA)
    a.pagar_como_particular("C1", "maria", AHORA)
    c = a.obtener_cita("C1")
    assert c.estado == EstadoCita.AGENDADA and c.aseguradora_id is None and c.autorizacion is None


@pytest.mark.traza("US-09")
def test_medico_no_puede_atender_dentro_de_la_tolerancia():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    a.registrar_llegada("C1", dt(9, 10), Tolerancia())
    a.marcar_no_atendida_por_retraso("C1", "maria", dt(9, 11))
    assert a.obtener_cita("C1").estado == EstadoCita.NO_ATENDIDA_POR_RETRASO


# ----------------------------------------------------------- no-show y cierre
@pytest.mark.traza("US-14", "US-20", "CU-05")
def test_T8_no_show_solo_si_agendada_y_hora_pasada():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    with pytest.raises(TransicionDeEstatusInvalida):
        a.marcar_no_show("C1", "maria", dt(8, 59))      # aún no es la hora
    a.registrar_llegada("C1", dt(9), Tolerancia())
    a.cerrar_consulta("C1", CierreDeConsulta("reposo"), "maria", dt(10))
    with pytest.raises(TransicionDeEstatusInvalida):     # ya atendida
        a.marcar_no_show("C1", "maria", dt(11))
    a.agendar(cita("C2", h=11, exp="E2"), 0, AHORA)
    a.marcar_no_show("C2", "maria", dt(11, 31))
    assert a.obtener_cita("C2").estado == EstadoCita.NO_SHOW


@pytest.mark.traza("US-13")
def test_cerrar_consulta_registra_receta_y_estudios():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    a.registrar_llegada("C1", dt(9), Tolerancia())
    a.cerrar_consulta("C1", CierreDeConsulta("paracetamol", ("biometría",), True), "maria", dt(10))
    c = a.obtener_cita("C1")
    assert c.estado == EstadoCita.ATENDIDA and c.cierre.estudios == ("biometría",)
    assert c.bloquea_franja  # una cita atendida sigue ocupando su franja histórica


@pytest.mark.traza("US-06", "US-21")
def test_confirmacion_requiere_envio_previo():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    with pytest.raises(TransicionDeEstatusInvalida):
        a.registrar_respuesta_de_confirmacion("C1", RespuestaDeConfirmacion.CONFIRMADA, AHORA)
    a.registrar_envio_de_confirmacion("C1", "whatsapp", AHORA)
    a.registrar_respuesta_de_confirmacion("C1", RespuestaDeConfirmacion.CONFIRMADA, AHORA)
    assert a.obtener_cita("C1").confirmacion.respuesta == RespuestaDeConfirmacion.CONFIRMADA


# ------------------------------------------------------------ jornada cancelada
@pytest.mark.traza("US-11", "CU-03")
def test_T7_cancelar_jornada_con_tres_citas_las_marca_afectadas_en_orden():
    a = agenda()
    for i, h in enumerate((11, 9, 10)):
        a.agendar(cita(f"C{i}", h=h, exp=f"E{i}"), 0, AHORA)
    afectadas = a.cancelar_jornada("A", "maria", MotivoDeCambio("enfermedad"), AHORA)
    assert [c.franja.inicio.hour for c in afectadas] == [9, 10, 11]        # la más próxima primero
    assert all(c.estado == EstadoCita.AFECTADA for c in afectadas)
    assert not a.jornadas[0].contiene(franja(9)) and a.jornadas[0].cancelada_en == AHORA
    tipos = [type(e) for e in a.recoger_eventos()]
    assert tipos.count(ev.CitaAfectadaPorJornada) == 3 and ev.JornadaCancelada in tipos
    with pytest.raises(FranjaFueraDeJornada):
        a.cancelar_jornada("A", "maria", MOT, AHORA)                        # ya cancelada


@pytest.mark.traza("US-11")
def test_cancelar_solo_una_jornada_o_todas():
    a = agenda(jornadas=(("A", 9, 13), ("B", 14, 17)))
    a.agendar(cita("C1"), 0, AHORA)
    a.agendar(cita("C2", "B", 14, exp="E2"), 0, AHORA)
    a.cancelar_jornada("B", "maria", MOT, AHORA)
    assert a.obtener_cita("C1").estado == EstadoCita.AGENDADA
    assert a.obtener_cita("C2").estado == EstadoCita.AFECTADA
    a.cancelar_jornada(None, "maria", MOT, AHORA)                            # todas las que queden
    assert a.obtener_cita("C1").estado == EstadoCita.AFECTADA


@pytest.mark.traza("US-09", "US-11", "CU-03")
def test_reagendador_crea_cita_vinculada_y_si_no_hay_lugar_no_cambia_nada():
    origen = agenda()
    origen.agendar(cita("C1"), 0, AHORA)
    origen.cancelar_jornada("A", "maria", MOT, AHORA)
    destino = AgendaMedica("M1", HOY + timedelta(days=1))
    destino.abrir_jornada(Jornada("JD", "A", franja(9, dur=240, dia=HOY + timedelta(days=1))))
    nueva = Reagendador().reagendar(origen, destino, "C1", franja(9, dia=HOY + timedelta(days=1)), "A", 0,
                                    "maria", AHORA, "C9")
    assert nueva.cita_origen_id == "C1" and nueva.estado == EstadoCita.AGENDADA
    assert origen.obtener_cita("C1").estado == EstadoCita.REAGENDADA
    assert origen.obtener_cita("C1").reagendada_en == AHORA
    # destino sin lugar: la cita de origen no cambia
    o2 = agenda()
    o2.agendar(cita("D1", h=10, exp="E5"), 0, AHORA)
    o2.cancelar_jornada("A", "maria", MOT, AHORA)
    with pytest.raises(FranjaFueraDeJornada):
        Reagendador().reagendar(o2, destino, "D1", franja(18, dia=HOY + timedelta(days=1)), "A", 0,
                                "maria", AHORA, "D9")
    assert o2.obtener_cita("D1").estado == EstadoCita.AFECTADA


def test_reagendar_una_cita_no_afectada_es_invalido():
    a = agenda()
    a.agendar(cita("C1"), 0, AHORA)
    with pytest.raises(TransicionDeEstatusInvalida):
        Reagendador().reagendar(a, a, "C1", franja(10), "A", 0, "maria", AHORA, "C2")
