from datetime import date, timedelta

import pytest

from src.application import comandos as cmd
from src.application import consultas as q
from src.application.puertos import EstadoDeNotificacion, Mensaje
from src.domain.errores import (CitaSolapadaDelPaciente, ConflictoDeVersion, DatosInvalidos, HorarioNoDisponible,
                                PacienteDuplicado, PacienteNoEncontrado, SobrecupoExcedido,
                                TransicionDeEstatusInvalida, MedicoNoEncontrado, CatalogoNoEncontrado,
                                CitaNoEncontrada)
from src.domain.value_objects import CierreDeConsulta
from src.infrastructure.notificador import NotificadorPorCanal
from src.infrastructure.unit_of_work_sql import UnitOfWorkSql
from tests.conftest import AHORA, HOY, dt, franja

pytestmark = pytest.mark.integracion


def cita_de(contenedor, cita_id):
    return contenedor.consultas.cita(cita_id)


# ---------------------------------------------------------------- CU-01
@pytest.mark.traza("US-04", "US-05", "CU-01")
def test_agendar_guarda_la_cita_y_bloquea_el_horario(mundo):
    r = mundo.agendar()
    assert r.estatus == "agendada"
    disp = mundo.c.consultas.disponibilidad(q.ConsultarDisponibilidadDelMedico(HOY, "M1", solo_libres=True))[0]
    horas = [f.inicio.hour * 60 + f.inicio.minute for f in disp.sucursales[0].franjas]
    assert 9 * 60 not in horas and 9 * 60 + 30 in horas


@pytest.mark.traza("US-05", "CU-01", "ADR-002")
def test_T1_otra_sucursal_no_puede_tomar_el_horario_del_mismo_medico(mundo):
    mundo.agendar("M1", "A", 10, expediente=mundo.p1)
    with pytest.raises(HorarioNoDisponible):
        mundo.agendar("M1", "A", 10, expediente=mundo.p2)


@pytest.mark.traza("US-10", "CU-01")
def test_T2_sobrecupo_por_medico_desde_la_base(mundo):
    mundo.agendar("M2", "A", 9, expediente=mundo.p1)
    mundo.agendar("M2", "A", 9, expediente=mundo.p2)
    mundo.agendar("M2", "A", 9, expediente=mundo.p3)
    mundo.c.pacientes.registrar_paciente(cmd.RegistrarPacienteCommand("Dani", "8110000004"))
    with pytest.raises(SobrecupoExcedido):
        mundo.agendar("M2", "A", 9, expediente="EXP-000004")
    mundo.c.catalogo.definir_sobrecupo("M2", 3)
    mundo.agendar("M2", "A", 9, expediente="EXP-000004")


@pytest.mark.traza("US-12", "CU-01", "ADR-005")
def test_T4_aseguradora_que_exige_autorizacion_deja_la_cita_pendiente(mundo):
    r = mundo.agendar(expediente=mundo.p3, aseguradora_id="ASEG-AUT")
    assert (r.estatus, r.autorizacion) == ("pendiente_autorizacion", "pendiente")
    assert any("48 h" in a for a in r.advertencias)  # la cita es en 2 h y la aseguradora pide 48 h
    # la franja queda bloqueada mientras está pendiente
    with pytest.raises(HorarioNoDisponible):
        mundo.agendar(h=9, expediente=mundo.p2)
    mundo.c.agendamiento.registrar_autorizacion(cmd.RegistrarAutorizacionCommand(r.cita_id, "AUT-77", "maria"))
    assert cita_de(mundo.c, r.cita_id).estado == "agendada"


@pytest.mark.traza("US-12")
def test_con_numero_de_autorizacion_queda_agendada_y_sin_exigencia_no_hay_autorizacion(mundo):
    r = mundo.agendar(expediente=mundo.p3, aseguradora_id="ASEG-AUT", numero_autorizacion="AUT-1")
    assert (r.estatus, r.autorizacion) == ("agendada", "otorgada")
    r2 = mundo.agendar(h=10, aseguradora_id="PARTICULAR-POLIZA")
    assert r2.autorizacion is None


@pytest.mark.traza("US-12")
def test_sin_autorizacion_el_paciente_puede_pagar_como_particular(mundo):
    r = mundo.agendar(expediente=mundo.p3, aseguradora_id="ASEG-AUT")
    out = mundo.c.agendamiento.pagar_como_particular(cmd.PagarComoParticularCommand(r.cita_id, "maria"))
    assert out.estatus == "agendada" and cita_de(mundo.c, r.cita_id).aseguradora_id is None


@pytest.mark.traza("US-04")
def test_validaciones_de_referencia_y_pasado(mundo):
    with pytest.raises(PacienteNoEncontrado):
        mundo.agendar(expediente="EXP-999999")
    with pytest.raises(MedicoNoEncontrado):
        mundo.agendar(medico="NOPE")
    with pytest.raises(CatalogoNoEncontrado):
        mundo.agendar(sucursal="Z")
    with pytest.raises(CatalogoNoEncontrado):
        mundo.agendar(aseguradora_id="NOPE")
    with pytest.raises(DatosInvalidos):
        mundo.agendar(especialidad="CARD")  # M1 no es cardiólogo
    mundo.reloj.fijar(dt(10))
    with pytest.raises(DatosInvalidos):
        mundo.agendar(h=9)  # en el pasado


@pytest.mark.traza("US-04", "US-05")
def test_un_paciente_no_puede_tener_dos_citas_simultaneas_en_dos_sucursales(mundo):
    mundo.agendar("M1", "A", 10, expediente=mundo.p1)
    with pytest.raises(CitaSolapadaDelPaciente):
        mundo.agendar("M3", "B", 10, expediente=mundo.p1)
    mundo.agendar("M3", "B", 11, expediente=mundo.p1)  # otra hora sí


# ---------------------------------------------------------------- CU-04
@pytest.mark.traza("US-17", "US-19", "CU-04", "ADR-003")
def test_cancelar_deja_auditoria_con_usuario_fecha_y_motivo(mundo):
    r = mundo.agendar()
    mundo.c.agendamiento.cancelar_cita(cmd.CancelarCitaCommand(r.cita_id, "maria", "Paciente enfermo"))
    reg = mundo.c.consultas.auditoria(r.cita_id)
    assert len(reg) == 1
    assert (reg[0].usuario, reg[0].motivo, reg[0].tipo, reg[0].fecha) == ("maria", "Paciente enfermo", "CitaCancelada", AHORA)
    mundo.agendar(h=9, expediente=mundo.p2)  # el horario quedó libre


@pytest.mark.traza("US-17", "US-19", "CU-04")
def test_cancelar_sin_motivo_se_rechaza_y_no_deja_rastro(mundo):
    r = mundo.agendar()
    with pytest.raises(DatosInvalidos):
        mundo.c.agendamiento.cancelar_cita(cmd.CancelarCitaCommand(r.cita_id, "maria", " "))
    assert cita_de(mundo.c, r.cita_id).estado == "agendada"
    assert mundo.c.consultas.auditoria(r.cita_id) == []


@pytest.mark.traza("US-19", "US-17", "CU-04")
def test_modificar_cita_audita_el_cambio(mundo):
    r = mundo.agendar()
    mundo.c.agendamiento.modificar_cita(cmd.ModificarCitaCommand(r.cita_id, franja(14), "B", "maria", "Cambio de sede"))
    c = cita_de(mundo.c, r.cita_id)
    assert (c.sucursal_id, c.inicio) == ("B", dt(14))
    assert mundo.c.consultas.auditoria(r.cita_id)[0].tipo == "CitaModificada"
    with pytest.raises(CatalogoNoEncontrado):
        mundo.c.agendamiento.modificar_cita(cmd.ModificarCitaCommand(r.cita_id, franja(15), "Z", "maria", "x"))


@pytest.mark.traza("US-17", "CU-04", "ADR-003")
def test_T5_si_falla_la_auditoria_no_se_cancela_nada(mundo, monkeypatch):
    r = mundo.agendar()

    def falla(self, registro):
        raise RuntimeError("fallo al guardar la auditoría")

    monkeypatch.setattr("src.infrastructure.repositorios_sql.AuditoriaSql.agregar", falla)
    with pytest.raises(RuntimeError):
        mundo.c.agendamiento.cancelar_cita(cmd.CancelarCitaCommand(r.cita_id, "maria", "motivo"))
    monkeypatch.undo()
    assert cita_de(mundo.c, r.cita_id).estado == "agendada"      # transacción deshecha
    assert mundo.c.consultas.auditoria(r.cita_id) == []


# --------------------------------------------------------------- ADR-002
@pytest.mark.traza("US-05", "ADR-002")
def test_T6_dos_confirmaciones_simultaneas_la_segunda_falla_por_version(mundo, contenedor):
    sf = contenedor.session_factory
    u1, u2 = UnitOfWorkSql(sf), UnitOfWorkSql(sf)
    with u1, u2:
        a1 = u1.agendas.obtener_por_medico_y_fecha("M1", HOY)
        a2 = u2.agendas.obtener_por_medico_y_fecha("M1", HOY)
        assert a1.version == a2.version >= 1
        from src.domain.cita import Cita
        a1.agendar(Cita("X1", mundo.p1, "M1", "A", franja(9)), 0, AHORA)
        a2.agendar(Cita("X2", mundo.p2, "M1", "A", franja(9)), 0, AHORA)
        u1.agendas.guardar(a1)
        u1.confirmar()
        with pytest.raises(ConflictoDeVersion):
            u2.agendas.guardar(a2)
    assert [c.id for c in contenedor.consultas.citas(q.ConsultarCitas(HOY, "M1"))] == ["X1"]


@pytest.mark.traza("US-05", "ADR-002")
def test_conflicto_de_version_se_traduce_en_horario_no_disponible(mundo, monkeypatch):
    from src.infrastructure.repositorios_sql import AgendaMedicaSql
    original = AgendaMedicaSql.guardar

    def guardar_con_conflicto(self, agenda):
        raise ConflictoDeVersion("otra recepción guardó antes")

    monkeypatch.setattr(AgendaMedicaSql, "guardar", guardar_con_conflicto)
    with pytest.raises(HorarioNoDisponible):
        mundo.agendar()
    monkeypatch.setattr(AgendaMedicaSql, "guardar", original)
    assert mundo.agendar().estatus == "agendada"


# ---------------------------------------------------------------- CU-02
@pytest.mark.traza("US-07", "US-08", "US-09", "CU-02")
def test_llegada_a_tiempo_en_tolerancia_y_con_exceso_de_retraso(mundo):
    a = mundo.agendar(h=9, expediente=mundo.p1).cita_id
    b = mundo.agendar(h=10, expediente=mundo.p2).cita_id
    c = mundo.agendar(h=11, expediente=mundo.p3).cita_id
    ra = mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(a, hora_llegada=dt(9)))
    rb = mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(b, hora_llegada=dt(10, 15)))
    rc = mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(c, hora_llegada=dt(11, 16)))
    assert (ra.resultado, rb.resultado, rc.resultado) == ("a_tiempo", "consultar_medico", "no_atendida_por_retraso")
    assert (ra.estatus, rb.estatus, rc.estatus) == ("presente", "presente", "no_atendida_por_retraso")
    assert "consultar al médico" in rb.mensaje


@pytest.mark.traza("US-07")
def test_llegada_usa_el_reloj_cuando_no_se_indica_hora(mundo):
    r = mundo.agendar(h=9).cita_id
    mundo.reloj.fijar(dt(8, 55))
    assert mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(r)).hora_llegada == dt(8, 55)


@pytest.mark.traza("US-22", "CU-02")
def test_en_cada_visita_se_valida_telefono_y_aseguradora(mundo):
    r = mundo.agendar(h=9, expediente=mundo.p1).cita_id
    mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(
        r, hora_llegada=dt(9), telefono="8199999999", aseguradora_id="ASEG-AUT", actualiza_aseguradora=True))
    p = mundo.c.pacientes.buscar(expediente=mundo.p1)
    assert p.contacto.telefono == "8199999999" and p.aseguradora_id == "ASEG-AUT"


@pytest.mark.traza("US-09", "CU-02")
def test_medico_no_puede_atender_dentro_de_la_tolerancia_y_se_reagenda(mundo):
    r = mundo.agendar(h=9).cita_id
    mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(r, hora_llegada=dt(9, 10)))
    out = mundo.c.atencion.marcar_no_atendida_por_retraso(cmd.MarcarNoAtendidaPorRetrasoCommand(r))
    assert out.estatus == "no_atendida_por_retraso"
    nueva = mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(r, "M1", franja(11), "A", "maria"))
    assert nueva.estatus == "agendada"
    assert cita_de(mundo.c, nueva.cita_nueva_id).cita_origen_id == r
    assert cita_de(mundo.c, r).estado == "reagendada"


# ---------------------------------------------------------------- CU-05
@pytest.mark.traza("US-14", "US-20", "CU-05", "ADR-005")
def test_no_show_suma_al_historial_y_la_politica_alerta_al_llegar_al_umbral(mundo):
    for i, h in enumerate((9, 10, 11)):
        r = mundo.agendar(h=h).cita_id if i == 0 else mundo.agendar(h=h, expediente=mundo.p1).cita_id
        mundo.reloj.fijar(dt(h, 40))
        out = mundo.c.atencion.marcar_no_show(cmd.MarcarNoShowCommand(r))
        assert out.estatus == "no_show"
    assert out.advertencias and "3 no-shows" in out.advertencias[0]
    h = mundo.c.consultas.historial_no_shows(q.ConsultarHistorialDeNoShows(mundo.p1))
    assert h.total == 3 and len(h.fechas) == 3 and h.alerta
    mundo.reloj.fijar(AHORA + timedelta(days=0, hours=3))
    r = mundo.agendar(h=12, expediente=mundo.p1)
    assert any("no-shows" in a for a in r.advertencias)
    assert mundo.c.consultas.historial_no_shows(q.ConsultarHistorialDeNoShows("NOPE")) is None


@pytest.mark.traza("US-20", "CU-05")
def test_T8_no_show_a_cita_atendida_se_rechaza_en_el_servicio(mundo):
    r = mundo.agendar(h=9).cita_id
    mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(r, hora_llegada=dt(9)))
    mundo.c.atencion.cerrar_consulta(cmd.CerrarConsultaCommand(r, CierreDeConsulta("reposo")))
    mundo.reloj.fijar(dt(12))
    with pytest.raises(TransicionDeEstatusInvalida):
        mundo.c.atencion.marcar_no_show(cmd.MarcarNoShowCommand(r))


@pytest.mark.traza("US-13")
def test_cierre_de_consulta_con_receta_estudios_y_nueva_cita_en_una_transaccion(mundo):
    r = mundo.agendar(h=9).cita_id
    mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(r, hora_llegada=dt(9)))
    nueva = cmd.AgendarCitaCommand("M1", franja(9, dia=HOY + timedelta(days=1)), "A", mundo.p1, "MG", "seguimiento")
    out = mundo.c.atencion.cerrar_consulta(cmd.CerrarConsultaCommand(
        r, CierreDeConsulta("amoxicilina", ("biometría hemática",), True), "maria", nueva))
    assert out.estatus == "atendida" and "Nueva cita" in out.advertencias[0]
    assert len(mundo.c.consultas.citas(q.ConsultarCitas(HOY + timedelta(days=1), "M1"))) == 1
    # si la nueva cita no cabe, no se cierra la consulta (todo o nada)
    r2 = mundo.agendar(h=10, expediente=mundo.p2).cita_id
    mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(r2, hora_llegada=dt(10)))
    mala = cmd.AgendarCitaCommand("M1", franja(9, dia=HOY + timedelta(days=1)), "A", mundo.p3, "MG")
    with pytest.raises(HorarioNoDisponible):
        mundo.c.atencion.cerrar_consulta(cmd.CerrarConsultaCommand(r2, CierreDeConsulta(), "maria", mala))
    assert cita_de(mundo.c, r2).estado == "presente"


# ---------------------------------------------------------------- CU-03
@pytest.mark.traza("US-11", "US-23", "US-24", "CU-03")
def test_T7_cancelar_jornada_listar_afectados_reagendar_y_medir_tiempo(mundo):
    for h, e in ((10, mundo.p1), (9, mundo.p2), (11, mundo.p3)):
        mundo.agendar("M1", "A", h, expediente=e)
    afectadas = mundo.c.jornadas.cancelar_jornada(cmd.CancelarJornadaCommand("M1", HOY, "maria", "Enfermedad", "A"))
    assert [a.hora_original.hour for a in afectadas] == [9, 10, 11]
    lista = mundo.c.consultas.citas_afectadas(q.ConsultarCitasAfectadas("M1", HOY, "A"))
    assert [x.estado_reagendado for x in lista] == ["pendiente"] * 3
    assert lista[0].telefono == "8110000002" and lista[0].paciente == "Beto Ruiz"
    # reagenda 1 con otro médico, 1 mismo médico otro día; el 3.º no acepta y se cancela
    mundo.reloj.fijar(AHORA + timedelta(minutes=45))
    mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(lista[0].cita_id, "M3", franja(9), "B", "maria"))
    mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(
        lista[1].cita_id, "M1", franja(9, dia=HOY + timedelta(days=1)), "A", "maria"))
    mundo.c.agendamiento.cancelar_cita(cmd.CancelarCitaCommand(lista[2].cita_id, "maria", "El paciente no acepta"))
    lista = mundo.c.consultas.citas_afectadas(q.ConsultarCitasAfectadas("M1", HOY))
    assert [x.estado_reagendado for x in lista] == ["reagendada", "reagendada", "cancelada"]
    assert lista[0].nueva_cita_id is not None
    rep = mundo.c.consultas.reporte(q.ObtenerReporteConsolidado(HOY, HOY + timedelta(days=1)))
    assert rep.tiempo_promedio_reagendado_min == 45.0
    # disponibilidad: la jornada cancelada ya no se ofrece
    disp = mundo.c.consultas.disponibilidad(q.ConsultarDisponibilidadDelMedico(HOY, "M1", sucursal_id="A"))[0]
    assert disp.sucursales == []
    # se auditó cada afectada y cada reagendado (US-17)
    tipos = [r.tipo for r in mundo.c.consultas.auditoria(None)]
    assert tipos.count("CitaAfectadaPorJornada") == 3 and tipos.count("CitaReagendada") == 2


@pytest.mark.traza("US-11", "CU-03")
def test_reagendar_en_la_misma_agenda_y_error_si_no_hay_lugar(mundo):
    r = mundo.agendar("M1", "A", 9).cita_id
    mundo.c.jornadas.cancelar_jornada(cmd.CancelarJornadaCommand("M1", HOY, "maria", "x", "A"))
    # M1 sigue teniendo jornada en B a las 14:00 del mismo día: misma agenda, otra sucursal
    nueva = mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(r, "M1", franja(14), "B", "maria"))
    assert cita_de(mundo.c, nueva.cita_nueva_id).sucursal_id == "B"
    r2 = mundo.agendar("M2", "A", 9, expediente=mundo.p2).cita_id
    mundo.c.jornadas.cancelar_jornada(cmd.CancelarJornadaCommand("M2", HOY, "maria", "x"))
    with pytest.raises(HorarioNoDisponible):
        mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(r2, "M1", franja(14), "B", "maria"))
    with pytest.raises(MedicoNoEncontrado):
        mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(r2, "NOPE", franja(14), "B", "maria"))
    with pytest.raises(CatalogoNoEncontrado):
        mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand(r2, "M1", franja(14), "Z", "maria"))
    with pytest.raises(CitaNoEncontrada):
        mundo.c.jornadas.reagendar_cita_afectada(cmd.ReagendarCitaCommand("NOPE", "M1", franja(14), "B", "maria"))


@pytest.mark.traza("US-01")
def test_abrir_jornada_valida_catalogos(mundo):
    from src.domain.errores import JornadaTraslapada
    with pytest.raises(MedicoNoEncontrado):
        mundo.c.jornadas.abrir_jornada(cmd.AbrirJornadaCommand("NOPE", "A", franja(9)))
    with pytest.raises(CatalogoNoEncontrado):
        mundo.c.jornadas.abrir_jornada(cmd.AbrirJornadaCommand("M1", "Z", franja(9)))
    with pytest.raises(JornadaTraslapada):
        mundo.c.jornadas.abrir_jornada(cmd.AbrirJornadaCommand("M1", "B", franja(10)))


# ----------------------------------------------------- pacientes y catálogos
@pytest.mark.traza("US-02", "US-03")
def test_registro_de_paciente_expediente_unico_y_sin_duplicados(mundo):
    exp = mundo.c.pacientes.registrar_paciente(cmd.RegistrarPacienteCommand("Eva", "(81) 5555-0001", date(1990, 1, 2)))
    assert exp == "EXP-000004"
    with pytest.raises(PacienteDuplicado) as ex:
        mundo.c.pacientes.registrar_paciente(cmd.RegistrarPacienteCommand("Eva otra vez", "8155550001"))
    assert ex.value.expediente == exp
    assert mundo.c.pacientes.buscar(telefono="81 5555 0001").expediente == exp
    assert mundo.c.pacientes.buscar(expediente=exp).nacimiento == date(1990, 1, 2)
    with pytest.raises(PacienteNoEncontrado):
        mundo.c.pacientes.buscar(expediente="NOPE")
    with pytest.raises(PacienteNoEncontrado):
        mundo.c.pacientes.buscar()
    with pytest.raises(DatosInvalidos):
        mundo.c.pacientes.registrar_paciente(cmd.RegistrarPacienteCommand("  ", "8100000099"))
    with pytest.raises(PacienteNoEncontrado):
        mundo.c.pacientes.actualizar_paciente(cmd.ActualizarPacienteCommand("NOPE", telefono="8100000000"))


@pytest.mark.traza("US-10", "US-22")
def test_catalogos_y_sobrecupo(mundo):
    cat = mundo.c.catalogo
    assert {s.id for s in cat.listar("sucursales")} == {"A", "B"}
    assert cat.definir_sobrecupo("M1", 1).limite_sobrecupo.valor == 1
    with pytest.raises(MedicoNoEncontrado):
        cat.definir_sobrecupo("NOPE", 1)
    with pytest.raises(DatosInvalidos):
        cat.crear_sucursal("A", "repetida")
    with pytest.raises(DatosInvalidos):
        cat.definir_sobrecupo("M1", -1)
    with pytest.raises(DatosInvalidos):
        cat.crear_aseguradora("X", "x", True, -5)
    with pytest.raises(CatalogoNoEncontrado):
        cat.crear_medico("M9", "Dr. Nueve", ("NOPE",))
    assert len(cat.listar("especialidades")) == 2 and len(cat.listar("aseguradoras")) == 2


# ------------------------------------------------- confirmación (US-06/18/21)
@pytest.mark.traza("US-06", "US-18")
def test_confirmacion_un_dia_antes_por_el_canal_de_origen(mundo):
    mundo.agendar(h=9, expediente=mundo.p1, canal="whatsapp", dia=HOY + timedelta(days=1))
    mundo.agendar(h=10, expediente=mundo.p2, canal="telefono", dia=HOY + timedelta(days=1))
    res = mundo.c.confirmaciones.enviar_confirmaciones(cmd.EnviarConfirmacionesCommand(HOY + timedelta(days=1)))
    estados = {r["canal"]: r["estado"] for r in res}
    assert estados == {"whatsapp": "enviada", "telefono": "pendiente_gestion_manual"}
    assert mundo.c.confirmaciones.enviar_confirmaciones(cmd.EnviarConfirmacionesCommand(HOY + timedelta(days=1))) == []
    bandeja = mundo.c.consultas.notificaciones(10)
    assert {n.canal for n in bandeja} == {"whatsapp", "telefono"}   # incluye el aviso de CitaAgendada


@pytest.mark.traza("US-06", "US-21")
def test_respuesta_rechazada_libera_el_horario_y_confirmada_lo_mantiene(mundo):
    manana = HOY + timedelta(days=1)
    a = mundo.agendar(h=9, expediente=mundo.p1, dia=manana).cita_id
    b = mundo.agendar(h=10, expediente=mundo.p2, dia=manana).cita_id
    mundo.c.confirmaciones.enviar_confirmaciones(cmd.EnviarConfirmacionesCommand(manana))
    ra = mundo.c.confirmaciones.registrar_respuesta(cmd.RegistrarRespuestaDeConfirmacionCommand(a, "rechazada"))
    rb = mundo.c.confirmaciones.registrar_respuesta(cmd.RegistrarRespuestaDeConfirmacionCommand(b, "confirmada"))
    assert (ra["estatus"], rb["estatus"]) == ("cancelada", "agendada")
    assert cita_de(mundo.c, b).confirmacion == "confirmada"
    with pytest.raises(DatosInvalidos):
        mundo.c.confirmaciones.registrar_respuesta(cmd.RegistrarRespuestaDeConfirmacionCommand(b, "quizás"))
    assert mundo.c.consultas.auditoria(a)[0].tipo == "CitaCancelada"


@pytest.mark.traza("US-21")
def test_sin_respuesta_en_24_horas_se_libera_el_horario_con_auditoria(mundo):
    manana = HOY + timedelta(days=1)
    a = mundo.agendar(h=9, expediente=mundo.p1, dia=manana).cita_id
    b = mundo.agendar(h=10, expediente=mundo.p2, dia=manana).cita_id
    mundo.c.confirmaciones.enviar_confirmaciones(cmd.EnviarConfirmacionesCommand(manana))
    mundo.c.confirmaciones.registrar_respuesta(cmd.RegistrarRespuestaDeConfirmacionCommand(b, "confirmada"))
    mundo.reloj.fijar(AHORA + timedelta(hours=23))
    assert mundo.c.confirmaciones.liberar_sin_confirmacion() == []
    mundo.reloj.fijar(AHORA + timedelta(hours=24))
    assert mundo.c.confirmaciones.liberar_sin_confirmacion() == [a]
    assert cita_de(mundo.c, a).estado == "cancelada" and cita_de(mundo.c, b).estado == "agendada"
    reg = mundo.c.consultas.auditoria(a)[0]
    assert reg.usuario == "sistema" and "24 h" in reg.motivo


# ----------------------------------------------------------- reportes y notificador
@pytest.mark.traza("US-15", "US-24")
def test_reporte_consolidado_por_sucursal_y_medico(mundo):
    a = mundo.agendar("M1", "A", 9, expediente=mundo.p1).cita_id
    b = mundo.agendar("M1", "A", 10, expediente=mundo.p2).cita_id
    c = mundo.agendar("M1", "A", 11, expediente=mundo.p3).cita_id
    mundo.agendar("M3", "B", 9, expediente=mundo.p2)
    mundo.c.atencion.registrar_llegada(cmd.RegistrarLlegadaCommand(a, hora_llegada=dt(9)))
    mundo.c.atencion.cerrar_consulta(cmd.CerrarConsultaCommand(a, CierreDeConsulta()))
    mundo.reloj.fijar(dt(10, 45))
    mundo.c.atencion.marcar_no_show(cmd.MarcarNoShowCommand(b))
    mundo.c.agendamiento.cancelar_cita(cmd.CancelarCitaCommand(c, "maria", "x"))
    rep = mundo.c.consultas.reporte(q.ObtenerReporteConsolidado(HOY, HOY))
    fila = next(f for f in rep.filas if (f.sucursal_id, f.medico_id) == ("A", "M1"))
    assert (fila.agendadas, fila.atendidas, fila.no_shows, fila.canceladas) == (3, 1, 1, 1)
    assert fila.ocupacion_pct == 12.5   # 30 min atendida de 240 min de jornada (la no-show no ocupa)
    assert rep.total_citas == 4 and rep.total_no_shows == 1 and rep.tasa_no_show_pct == 25.0
    assert rep.tiempo_promedio_reagendado_min is None


@pytest.mark.traza("US-18", "ADR-003")
def test_notificador_no_falla_por_su_canal_y_no_deshace_la_cita(mundo, monkeypatch):
    n = NotificadorPorCanal(mundo.c.session_factory, mundo.reloj, "simulado")
    assert n.enviar(Mensaje("c", "e", "811", "whatsapp", "hola")).estado == EstadoDeNotificacion.ENVIADA
    assert n.enviar(Mensaje("c", "e", "811", "recepcion", "hola")).estado == EstadoDeNotificacion.PENDIENTE_GESTION_MANUAL
    off = NotificadorPorCanal(mundo.c.session_factory, mundo.reloj, "desactivado")
    assert off.enviar(Mensaje("c", "e", "811", "whatsapp", "hola")).estado == EstadoDeNotificacion.PENDIENTE_GESTION_MANUAL
    roto = NotificadorPorCanal(lambda: (_ for _ in ()).throw(RuntimeError("db caída")), mundo.reloj)
    assert roto.enviar(Mensaje("c", "e", "811", "whatsapp", "x")).estado == EstadoDeNotificacion.PENDIENTE_GESTION_MANUAL
    # un notificador que explota no deshace la cita ya confirmada
    monkeypatch.setattr(NotificadorPorCanal, "enviar", lambda self, m: (_ for _ in ()).throw(RuntimeError("x")))
    r = mundo.agendar(h=12)
    assert cita_de(mundo.c, r.cita_id).estado == "agendada"


def test_listados_de_citas_con_filtros(mundo):
    a = mundo.agendar(h=9).cita_id
    mundo.agendar(h=10, expediente=mundo.p2)
    assert len(mundo.c.consultas.citas(q.ConsultarCitas())) == 2
    assert len(mundo.c.consultas.citas(q.ConsultarCitas(estado="agendada", expediente=mundo.p1))) == 1
    assert mundo.c.consultas.cita("NOPE") is None
    assert mundo.c.consultas.cita(a).paciente == "Ana Pérez"
    disp = mundo.c.consultas.disponibilidad(q.ConsultarDisponibilidadDelMedico(HOY, especialidad="CARD"))
    assert [d.medico_id for d in disp] == ["M2"]
    todas = mundo.c.consultas.disponibilidad(q.ConsultarDisponibilidadDelMedico(HOY, "M1"))[0]
    assert {s.sucursal_id for s in todas.sucursales} == {"A", "B"}      # US-16: las dos sucursales a la vez
    assert todas.sucursales[0].franjas[0].estado == "ocupada"
