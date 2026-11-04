"""Ejecución de los CSV del PIA (120 casos + 20 transiciones) contra el dominio y la API.

El oráculo se calcula con Python plano directamente desde las filas crudas, sin usar las
Specifications: así se contrasta la implementación con una segunda ruta independiente.
"""
import csv
from decimal import Decimal

import pytest

from tests.conftest import RECEPCION
from tests.csv_modelo.modelo import DATOS, ejecutar_todo, escribir_resultados


def crudo(nombre):
    with open(DATOS / nombre, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def corrida():
    return ejecutar_todo()


def oraculo():
    act = {r["actor_id"]: r for r in crudo("actores.csv")}
    cat = {r["recurso_id"]: r for r in crudo("catalogo.csv")}
    ops = {r["operacion_id"]: r for r in crudo("operaciones.csv")}
    total, lineas = {}, {}
    for d in crudo("detalle_operaciones.csv"):
        total[d["operacion_id"]] = total.get(d["operacion_id"], Decimal(0)) + Decimal(cat[d["recurso_id"]]["precio_mxn"]) * int(d["cantidad"])
        lineas[d["operacion_id"]] = lineas.get(d["operacion_id"], 0) + 1
    return act, ops, total, lineas


@pytest.mark.traza("ADR-006")
def test_los_120_casos_coinciden_con_el_oraculo_independiente(corrida):
    act, ops, total, lineas = oraculo()
    assert len(corrida["casos"]) == 120
    for c in corrida["casos"]:
        o = ops[c["operacion_id"]]
        a = act[o["actor_id"]]
        if c["tipo_prueba"] == "validar_operacion":
            esperado = a["activo"] == "1" and lineas.get(o["operacion_id"], 0) > 0 and o["autorizado"] == "1"
        else:
            esperado = a["es_preferente"] == "1" and total.get(o["operacion_id"], Decimal(0)) >= 1500 and o["promocion_activa"] == "0"
        assert (c["resultado_alumno"] == "CUMPLE") is esperado, c["caso_id"]


@pytest.mark.traza("ADR-006")
def test_las_20_transiciones_coinciden_con_el_oraculo(corrida):
    act, ops, total, lineas = oraculo()
    assert len(corrida["transiciones"]) == 20
    for t in corrida["transiciones"]:
        o = ops[t["operacion_id"]]
        procesable = act[o["actor_id"]]["activo"] == "1" and lineas.get(o["operacion_id"], 0) > 0 and o["autorizado"] == "1"
        accion = t["accion_sugerida"]
        if not procesable and accion in ("aprobar", "completar", "repetir_aprobacion"):
            esperado = ("SOLICITADA", "EXCEPCION precondicion_no_cumplida")
        else:
            esperado = {
                "aprobar": ("CONFIRMADA", "OperacionConfirmada"),
                "completar": ("ATENDIDA", "OperacionConfirmada + OperacionAtendida"),
                "cancelar": ("CANCELADA", "OperacionCancelada"),
                "repetir_aprobacion": ("CONFIRMADA", "OperacionConfirmada | EXCEPCION transicion_de_estatus_invalida"),
                "saltar_estado": ("SOLICITADA", "EXCEPCION transicion_de_estatus_invalida"),
            }[accion]
        assert (t["resultado_alumno"], t["evidencia"]) == esperado, t["caso_id"]


def test_integridad_referencial_y_calidad_de_los_datos(corrida):
    d = corrida["datos"]
    assert (len(d["actores"]), len(d["recursos"]), len(d["operaciones"])) == (40, 20, 60)
    sin_detalle = [o for o in d["operaciones"].values() if not o.lineas]
    deshabilitadas = [ln for o in d["operaciones"].values() for ln in o.lineas if not ln.recurso.habilitado]
    assert len(sin_detalle) == 2 and len(deshabilitadas) == 6
    assert all(ln.cantidad > 0 and ln.cantidad <= ln.recurso.capacidad for o in d["operaciones"].values() for ln in o.lineas)
    assert all(c["operacion_id"] in d["operaciones"] for c in d["casos"])


def test_se_escriben_los_csv_de_resultados(tmp_path):
    escribir_resultados(tmp_path)
    filas = list(csv.DictReader(open(tmp_path / "resultados_casos_prueba.csv", encoding="utf-8-sig")))
    assert len(filas) == 120 and all(f["resultado_alumno"] in ("CUMPLE", "NO_CUMPLE") for f in filas)
    assert len(list(csv.DictReader(open(tmp_path / "resultados_transiciones.csv", encoding="utf-8-sig")))) == 20


def test_actores_del_csv_a_traves_de_la_api(client, mundo):
    """Contraste de códigos HTTP del paquete: 201, 200, 409, 404 y 422 con los 40 pacientes."""
    actores = crudo("actores.csv")
    expedientes = {}
    for i, a in enumerate(actores, 1):
        r = client.post("/pacientes", json={"nombre": a["nombre"], "telefono": f"8190{i:06d}"}, headers=RECEPCION)
        assert r.status_code == 201, r.text
        expedientes[a["actor_id"]] = r.json()["expediente"]
    assert len(set(expedientes.values())) == 40
    assert client.get("/pacientes", params={"expediente": expedientes["CITA-C009"]}, headers=RECEPCION).status_code == 200
    assert client.post("/pacientes", json={"nombre": "Repetido", "telefono": "8190000001"}, headers=RECEPCION).status_code == 409
    assert client.get("/pacientes", params={"expediente": "CITA-C999"}, headers=RECEPCION).status_code == 404
    assert client.post("/pacientes", json={"nombre": "", "telefono": "81"}, headers=RECEPCION).status_code == 422
