from datetime import timedelta

import pytest

from tests.conftest import ADMIN, DIRECCION, HOY, RECEPCION, dt

pytestmark = pytest.mark.integracion


def iso(h, m=0, dur=30, dia=HOY):
    ini = dt(h, m, dia)
    return {"inicio": ini.isoformat(), "fin": (ini + timedelta(minutes=dur)).isoformat()}


def cuerpo_cita(mundo, h=9, medico="M1", suc="A", exp=None, **extra):
    return {"medico_id": medico, "sucursal_id": suc, "expediente": exp or mundo.p1, "franja": iso(h),
            "especialidad": "MG", "motivo": "dolor", **extra}


def agendar(client, mundo, **kw):
    r = client.post("/citas", json=cuerpo_cita(mundo, **kw), headers=RECEPCION)
    assert r.status_code == 201, r.text
    return r.json()["cita_id"]


# ------------------------------------------------------------- seguridad
@pytest.mark.traza("US-17", "CU-04")
def test_sin_cabeceras_401_y_rol_invalido_401(client):
    assert client.get("/medicos").status_code == 401
    assert client.get("/medicos", headers={"X-Usuario": "x", "X-Rol": "medico"}).status_code == 401


@pytest.mark.traza("US-17", "CU-04")
def test_solo_recepcion_agenda_y_cancela(client, mundo):
    for h in (ADMIN, DIRECCION):
        r = client.post("/citas", json=cuerpo_cita(mundo), headers=h)
        assert r.status_code == 403 and r.json()["codigo"] == "permiso_denegado"
    cid = agendar(client, mundo)
    assert client.post(f"/citas/{cid}/cancelar", json={"motivo": "x"}, headers=ADMIN).status_code == 403
    assert client.get(f"/citas/{cid}", headers=ADMIN).status_code == 200


@pytest.mark.traza("US-15")
def test_reportes_solo_para_administrativo_y_direccion(client, mundo):
    p = {"desde": str(HOY), "hasta": str(HOY)}
    assert client.get("/consultas/reporte", params=p, headers=RECEPCION).status_code == 403
    assert client.get("/consultas/reporte", params=p, headers=DIRECCION).status_code == 200
    assert client.get("/consultas/reporte", params={"desde": str(HOY), "hasta": str(HOY - timedelta(days=1))},
                      headers=ADMIN).status_code == 422


# ---------------------------------------------------------- flujo completo
@pytest.mark.traza("US-04", "US-05", "US-17", "US-18", "CU-01", "CU-04")
def test_agendar_rechazar_duplicado_cancelar_y_auditar_por_api(client, mundo):
    cid = agendar(client, mundo)
    dup = client.post("/citas", json=cuerpo_cita(mundo, exp=mundo.p2), headers=RECEPCION)
    assert dup.status_code == 409 and dup.json()["codigo"] == "horario_no_disponible"
    r = client.post(f"/citas/{cid}/cancelar", json={"motivo": "Paciente viaja"}, headers=RECEPCION)
    assert r.status_code == 200 and r.json()["estatus"] == "cancelada"
    aud = client.get("/consultas/auditoria", params={"cita_id": cid}, headers=ADMIN).json()
    assert aud[0]["usuario"] == "maria" and aud[0]["motivo"] == "Paciente viaja"
    agendar(client, mundo, exp=mundo.p2)  # horario liberado
    assert client.get("/consultas/notificaciones", headers=RECEPCION).json()


@pytest.mark.traza("US-12", "CU-01")
def test_autorizacion_pendiente_y_registro_del_numero(client, mundo):
    r = client.post("/citas", json=cuerpo_cita(mundo, exp=mundo.p3, aseguradora_id="ASEG-AUT"), headers=RECEPCION)
    assert r.json()["estatus"] == "pendiente_autorizacion"
    cid = r.json()["cita_id"]
    assert client.post(f"/citas/{cid}/llegada", json={"hora_llegada": dt(9).isoformat()},
                       headers=RECEPCION).status_code == 409
    assert client.post(f"/citas/{cid}/autorizacion", json={"numero": "A-1"}, headers=RECEPCION).json()["estatus"] == "agendada"
    r2 = client.post("/citas", json=cuerpo_cita(mundo, h=10, exp=mundo.p3, aseguradora_id="ASEG-AUT"), headers=RECEPCION)
    assert client.post(f"/citas/{r2.json()['cita_id']}/pago-particular", headers=RECEPCION).json()["estatus"] == "agendada"


@pytest.mark.traza("US-07", "US-08", "US-09", "US-13", "CU-02")
def test_llegada_con_retraso_y_cierre_de_consulta_por_api(client, mundo):
    cid = agendar(client, mundo)
    r = client.post(f"/citas/{cid}/llegada", json={"hora_llegada": dt(9, 10).isoformat()}, headers=RECEPCION)
    assert r.json()["resultado"] == "consultar_medico" and r.json()["estatus"] == "presente"
    cierre = {"receta": "reposo", "estudios": ["rayos X"],
              "nueva_cita": cuerpo_cita(mundo, h=9) | {"franja": iso(9, dia=HOY + timedelta(days=1))}}
    r = client.post(f"/citas/{cid}/cierre", json=cierre, headers=RECEPCION)
    assert r.status_code == 200 and r.json()["estatus"] == "atendida", r.text
    assert client.post(f"/citas/{cid}/llegada", headers=RECEPCION).status_code == 409   # transición inválida



@pytest.mark.traza("US-14", "US-20", "CU-05")
def test_no_show_e_historial_por_api(client, mundo, reloj):
    cid = agendar(client, mundo)
    assert client.post(f"/citas/{cid}/no-show", headers=RECEPCION).status_code == 409   # aún no es la hora
    reloj.fijar(dt(9, 45))
    assert client.post(f"/citas/{cid}/no-show", headers=RECEPCION).json()["estatus"] == "no_show"
    h = client.get(f"/consultas/historial-no-shows/{mundo.p1}", headers=ADMIN).json()
    assert h["total"] == 1
    assert client.get("/consultas/historial-no-shows/NOPE", headers=ADMIN).status_code == 404


@pytest.mark.traza("US-11", "US-16", "CU-03")
def test_cancelar_jornada_y_reagendar_por_api(client, mundo):
    cid = agendar(client, mundo)
    r = client.post("/jornadas/cancelar", json={"medico_id": "M1", "fecha": str(HOY), "sucursal_id": "A",
                                                "motivo": "Enfermedad"}, headers=RECEPCION)
    assert r.status_code == 200 and r.json()[0]["estatus"] == "afectada"
    afect = client.get("/consultas/citas-afectadas", params={"medico_id": "M1", "fecha": str(HOY)}, headers=RECEPCION).json()
    assert afect[0]["paciente"] == "Ana Pérez" and afect[0]["estado_reagendado"] == "pendiente"
    nueva = client.post(f"/citas/{cid}/reagendar", json={"medico_id": "M3", "sucursal_id": "B", "franja": iso(9)},
                        headers=RECEPCION)
    assert nueva.status_code == 201 and nueva.json()["cita_origen_id"] == cid
    disp = client.get("/consultas/disponibilidad", params={"fecha": str(HOY), "medico_id": "M1"}, headers=RECEPCION).json()
    assert [s["sucursal_id"] for s in disp[0]["sucursales"]] == ["B"]


@pytest.mark.traza("US-01", "US-16")
def test_disponibilidad_por_especialidad_y_sucursal(client, mundo):
    r = client.get("/consultas/disponibilidad", params={"fecha": str(HOY), "especialidad": "MG", "sucursal_id": "A",
                                                        "solo_libres": True}, headers=RECEPCION)
    assert {m["medico_id"] for m in r.json()} == {"M1", "M2", "M3"}
    assert all(f["estado"] == "libre" for m in r.json() for s in m["sucursales"] for f in s["franjas"])


@pytest.mark.traza("US-02", "US-03", "US-22")
def test_pacientes_por_api(client, mundo):
    r = client.post("/pacientes", json={"nombre": "Nuevo", "telefono": "8120000000"}, headers=RECEPCION)
    assert r.status_code == 201 and r.json()["expediente"] == "EXP-000004"
    dup = client.post("/pacientes", json={"nombre": "Otro", "telefono": "81 2000 0000"}, headers=RECEPCION)
    assert dup.status_code == 409 and dup.json()["expediente"] == "EXP-000004"
    assert client.get("/pacientes", params={"telefono": "8120000000"}, headers=RECEPCION).json()["nombre"] == "Nuevo"
    assert client.get("/pacientes", headers=RECEPCION).status_code == 422
    assert client.get("/pacientes", params={"expediente": "NOPE"}, headers=RECEPCION).status_code == 404
    r = client.patch("/pacientes/EXP-000004", json={"telefono": "8133333333"}, headers=RECEPCION)
    assert r.json()["telefono"] == "8133333333"
    assert client.post("/pacientes", json={"nombre": "X", "telefono": "12"}, headers=RECEPCION).status_code == 422


@pytest.mark.traza("US-10")
def test_catalogos_y_sobrecupo_por_api(client, mundo):
    assert client.put("/medicos/M1/sobrecupo", json={"limite": 2}, headers=RECEPCION).json()["limite_sobrecupo"] == 2
    assert client.put("/medicos/M1/sobrecupo", json={"limite": -1}, headers=RECEPCION).status_code == 422
    assert client.put("/medicos/NOPE/sobrecupo", json={"limite": 1}, headers=RECEPCION).status_code == 404
    assert client.post("/medicos", json={"id": "M9", "nombre": "Dr. Nueve", "especialidades": ["MG"]}, headers=ADMIN).status_code == 201
    assert client.post("/sucursales", json={"id": "C", "nombre": "C"}, headers=RECEPCION).status_code == 201
    assert client.post("/especialidades", json={"id": "PED", "nombre": "Pediatría"}, headers=RECEPCION).status_code == 201
    assert client.post("/aseguradoras", json={"id": "Z", "nombre": "Z", "exige_autorizacion": True}, headers=RECEPCION).status_code == 201
    for ruta in ("sucursales", "especialidades", "aseguradoras", "medicos"):
        assert client.get(f"/{ruta}", headers=DIRECCION).status_code == 200
    r = client.post("/jornadas", json={"medico_id": "M9", "sucursal_id": "C", "franja": iso(9, dur=60)}, headers=RECEPCION)
    assert r.status_code == 201 and r.json()["jornada_id"]
    assert client.post("/jornadas", json={"medico_id": "M9", "sucursal_id": "A", "franja": iso(9, 30, 60)},
                       headers=RECEPCION).status_code == 409


@pytest.mark.traza("US-06", "US-18", "US-21")
def test_confirmaciones_por_api(client, mundo):
    manana = HOY + timedelta(days=1)
    r = client.post("/citas", json=cuerpo_cita(mundo) | {"franja": iso(9, dia=manana), "canal": "whatsapp"}, headers=RECEPCION)
    cid = r.json()["cita_id"]
    env = client.post("/citas/confirmaciones/enviar", json={"fecha": str(manana)}, headers=RECEPCION)
    assert env.json()[0]["estado"] == "enviada"
    r = client.post(f"/citas/{cid}/confirmacion", json={"respuesta": "confirmada"}, headers=RECEPCION)
    assert r.json()["respuesta"] == "confirmada"
    assert client.post(f"/citas/{cid}/confirmacion", json={"respuesta": "tal vez"}, headers=RECEPCION).status_code == 422
    assert client.post("/citas/confirmaciones/liberar-sin-respuesta", headers=RECEPCION).json() == {"liberadas": [], "total": 0}


@pytest.mark.traza("US-04")
def test_errores_http_y_validacion(client, mundo):
    assert client.get("/citas/NOPE", headers=RECEPCION).status_code == 404
    assert client.post("/citas", json={"medico_id": "M1"}, headers=RECEPCION).status_code == 422
    r = client.post("/citas", json=cuerpo_cita(mundo, h=20), headers=RECEPCION)
    assert r.status_code == 422 and r.json()["codigo"] == "franja_fuera_de_jornada"
    assert client.post("/citas", json=cuerpo_cita(mundo) | {"canal": "paloma"}, headers=RECEPCION).status_code == 422
    assert client.get("/citas", params={"fecha": str(HOY)}, headers=RECEPCION).status_code == 200
    assert client.get("/health").json()["estado"] == "ok"
    assert client.get("/", follow_redirects=False).status_code in (302, 307)


@pytest.mark.traza("US-04", "ADR-004")
def test_openapi_documenta_la_api(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "MediNova API"
    assert "/citas" in spec["paths"] and "/consultas/disponibilidad" in spec["paths"]
    assert {"X-Usuario", "X-Rol"} <= {s["name"] for s in spec["components"]["securitySchemes"].values()}
    assert client.get("/docs").status_code == 200


@pytest.mark.traza("US-14", "ADR-007")
def test_reloj_simulable_solo_cuando_se_habilita(engine):
    from fastapi.testclient import TestClient

    from src.api.main import crear_app
    from src.infrastructure.config import Configuracion
    cfg = Configuracion(database_url="sqlite://", reloj_simulable=True)
    with TestClient(crear_app(cfg)) as c:
        r = c.put("/demo/reloj", json={"ahora": "2030-01-01T10:00:00"})
        assert r.json()["ahora"] == "2030-01-01T10:00:00"
        assert c.get("/demo/reloj").json()["ahora"] == "2030-01-01T10:00:00"
        c.put("/demo/reloj", json={"ahora": None})
        assert c.get("/demo/reloj").json()["ahora"] != "2030-01-01T10:00:00"
    with TestClient(crear_app(Configuracion(database_url="sqlite://"))) as c:
        assert c.get("/demo/reloj").status_code == 404
