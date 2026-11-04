"""Pruebas unitarias del modelo del paquete CSV (Specifications AND/OR/NOT, máquina de estados, eventos)."""
from decimal import Decimal

import pytest

from src.domain.errores import TransicionDeEstatusInvalida
from tests.csv_modelo.modelo import (BENEFICIO_REFERENCIA, PUEDE_PROCESARSE, ActorActivo, ActorPreferente, Actor,
                                     DetalleNoVacio, EstadoOperacion, Linea, LineasValidas, Operacion,
                                     PrecondicionNoCumplida, PromocionActiva, Recurso)

R = Recurso("P", "Consulta", Decimal("500.00"), 10, True)


def op(activo=True, pref=False, aut=True, promo=False, lineas=((R, 1),)):
    a = Actor("A", "Paciente", pref, activo, "Monterrey")
    return Operacion("O", a, EstadoOperacion.SOLICITADA, "2026-10-01", promo, aut, [Linea(r, c) for r, c in lineas])


def test_total_con_decimal_sin_error_de_flotante():
    r = Recurso("P", "x", Decimal("0.10"), 100, True)
    assert op(lineas=((r, 3),)).total == Decimal("0.30")


@pytest.mark.parametrize("kw,esperado", [({}, True), ({"activo": False}, False), ({"aut": False}, False), ({"lineas": ()}, False)])
def test_puede_procesarse_compone_tres_specifications_con_and(kw, esperado):
    assert PUEDE_PROCESARSE.es_satisfecha_por(op(**kw)) is esperado


@pytest.mark.parametrize("pref,promo,cant,esperado", [
    (True, False, 3, True),    # 1500 exactos, preferente, sin promoción
    (True, False, 2, False),   # 1000 < 1500
    (False, False, 3, False),  # no preferente
    (True, True, 3, False),    # promoción activa (NOT)
])
def test_beneficio_referencia_and_not_con_umbral_inclusivo(pref, promo, cant, esperado):
    assert BENEFICIO_REFERENCIA.es_satisfecha_por(op(pref=pref, promo=promo, lineas=((R, cant),))) is esperado


def test_or_y_not_de_specifications():
    o = op(activo=False, pref=True)
    assert (ActorActivo() | ActorPreferente()).es_satisfecha_por(o)
    assert (~ActorActivo()).es_satisfecha_por(o)
    assert not (ActorActivo() & DetalleNoVacio()).es_satisfecha_por(o)
    assert not PromocionActiva().es_satisfecha_por(o)


def test_lineas_validas_detecta_recurso_deshabilitado_y_cantidades():
    off = Recurso("Q", "x", Decimal("1"), 5, False)
    assert not LineasValidas().es_satisfecha_por(op(lineas=((off, 1),)))
    assert not LineasValidas().es_satisfecha_por(op(lineas=((R, 11),)))   # excede capacidad
    assert not LineasValidas().es_satisfecha_por(op(lineas=((R, 0),)))    # cantidad cero
    assert LineasValidas().es_satisfecha_por(op(lineas=((R, 10),)))


def test_flujo_feliz_emite_eventos_en_orden():
    o = op()
    o.aprobar()
    o.atender()
    assert o.estado is EstadoOperacion.ATENDIDA
    assert [e.nombre for e in o.eventos] == ["OperacionConfirmada", "OperacionAtendida"]


@pytest.mark.parametrize("secuencia", [["atender"], ["aprobar", "aprobar"], ["aprobar", "atender", "cancelar"], ["cancelar", "aprobar"]])
def test_transiciones_invalidas(secuencia):
    o = op()
    with pytest.raises(TransicionDeEstatusInvalida):
        for paso in secuencia:
            getattr(o, paso)()


def test_aprobar_exige_precondiciones_y_no_cambia_estado():
    o = op(activo=False)
    with pytest.raises(PrecondicionNoCumplida):
        o.aprobar()
    assert o.estado is EstadoOperacion.SOLICITADA and o.eventos == []
