import pytest

from src.domain.errores import DatosInvalidos, TransicionDeEstatusInvalida
from src.domain.estados import (TRANSICIONES, Disparador, EstadoCita, ESTADOS_FINALES,
                                MaquinaDeEstadosDeCita as M)
from src.domain.value_objects import (Contacto, FranjaHoraria, LimiteDeSobrecupo, MotivoDeCambio,
                                      NumeroDeExpediente, ResultadoDeLlegada, Tolerancia)
from tests.conftest import dt

pytestmark = pytest.mark.traza("US-07", "US-09", "US-20", "CU-02", "ADR-006")


@pytest.mark.parametrize("origen,disp,destino", [(o, d, t) for (o, d), t in TRANSICIONES.items()])
def test_cada_transicion_declarada_es_valida(origen, disp, destino):
    assert M.siguiente(origen, disp) == destino


def test_todas_las_demas_transiciones_se_rechazan():
    for estado in EstadoCita:
        for disp in Disparador:
            if (estado, disp) not in TRANSICIONES:
                with pytest.raises(TransicionDeEstatusInvalida):
                    M.siguiente(estado, disp)


def test_estados_finales_no_tienen_salidas():
    for e in ESTADOS_FINALES:
        assert M.permitidos(e) == []


def test_diagrama_mermaid_se_genera_desde_la_tabla():
    texto = M.a_mermaid()
    assert "stateDiagram-v2" in texto and "agendada --> presente: registrar_llegada" in texto
    assert texto.count("-->") >= len(TRANSICIONES)


@pytest.mark.traza("US-08", "US-09")
@pytest.mark.parametrize("minutos,esperado", [
    (-5, ResultadoDeLlegada.A_TIEMPO), (0, ResultadoDeLlegada.A_TIEMPO),
    (1, ResultadoDeLlegada.CONSULTAR_MEDICO), (14, ResultadoDeLlegada.CONSULTAR_MEDICO),
    (15, ResultadoDeLlegada.CONSULTAR_MEDICO), (16, ResultadoDeLlegada.NO_ATENDIDA_POR_RETRASO)])
def test_tolerancia_de_15_minutos(minutos, esperado):
    from datetime import timedelta
    assert Tolerancia().evaluar(dt(9), dt(9) + timedelta(minutes=minutos)) == esperado


def test_value_objects_validan_sus_datos():
    with pytest.raises(DatosInvalidos):
        FranjaHoraria(dt(10), dt(9))
    with pytest.raises(DatosInvalidos):
        LimiteDeSobrecupo(-1)
    with pytest.raises(DatosInvalidos):
        Contacto("123")
    with pytest.raises(DatosInvalidos):
        Contacto("8112345678", "sin-arroba")
    with pytest.raises(DatosInvalidos):
        MotivoDeCambio("  ")
    with pytest.raises(DatosInvalidos):
        NumeroDeExpediente(" ")
    assert Contacto("(81) 1234-5678").telefono_normalizado == "8112345678"
    assert FranjaHoraria(dt(9), dt(10)).minutos == 60
    assert FranjaHoraria(dt(9), dt(10)).se_solapa(FranjaHoraria(dt(9, 30), dt(10, 30)))
    assert not FranjaHoraria(dt(9), dt(10)).se_solapa(FranjaHoraria(dt(10), dt(11)))
