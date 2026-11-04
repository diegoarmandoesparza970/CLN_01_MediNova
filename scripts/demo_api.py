"""Guion de demostración en vivo: recorre las reglas y estados principales contra una API en ejecución.

Uso:  BASE_URL=http://localhost:8000 python -m scripts.demo_api
Requiere SEED_DEMO=true y RELOJ_SIMULABLE=true en el servidor (ver .env.example).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta

import httpx

BASE = os.environ.get("BASE_URL", "http://localhost:8000")
REC = {"X-Usuario": "maria", "X-Rol": "recepcion"}
ADM = {"X-Usuario": "luis", "X-Rol": "administrativo"}
http = httpx.Client(base_url=BASE, timeout=20)


def paso(titulo):
    print(f"\n=== {titulo}")


def llamar(metodo, ruta, headers=REC, esperado=None, **kw):
    r = http.request(metodo, ruta, headers=headers, **kw)
    cuerpo = r.json() if r.content else None
    resumen = json.dumps(cuerpo, ensure_ascii=False)[:230]
    print(f"{metodo} {ruta} -> {r.status_code}  {resumen}")
    if esperado and r.status_code != esperado:
        raise SystemExit(f"Se esperaba {esperado}, llegó {r.status_code}")
    return cuerpo


def f(dia, h, m=0, dur=30):
    ini = datetime.combine(dia, time(h, m))
    return {"inicio": ini.isoformat(), "fin": (ini + timedelta(minutes=dur)).isoformat()}


def main():
    hoy = datetime.fromisoformat(llamar("GET", "/demo/reloj")["ahora"]).date()
    d = hoy + timedelta(days=1)
    llamar("PUT", "/demo/reloj", json={"ahora": datetime.combine(d, time(8, 0)).isoformat()})
    pacientes = {p["nombre"]: p["expediente"] for p in
                 (llamar("GET", "/pacientes", params={"telefono": t})
                  for t in ("8112345678", "8187654321"))}
    p1, p2 = pacientes["Paciente Demo Uno"], pacientes["Paciente Demo Dos"]

    paso("1. Disponibilidad de MED-002 en sus dos sucursales (US-01, US-16)")
    llamar("GET", "/consultas/disponibilidad", params={"fecha": str(d), "medico_id": "MED-002", "solo_libres": True})

    paso("2. Agendar y rechazo por horario ocupado en otra sucursal (US-04, US-05)")
    base = {"medico_id": "MED-001", "sucursal_id": "CENTRO", "franja": f(d, 9), "especialidad": "MG", "motivo": "Dolor"}
    cita1 = llamar("POST", "/citas", json=base | {"expediente": p1, "canal": "whatsapp"}, esperado=201)["cita_id"]
    llamar("POST", "/citas", json=base | {"expediente": p2}, esperado=409)

    paso("3. Sobrecupo: MED-002 acepta hasta 2 extras (US-10)")
    s = {"medico_id": "MED-002", "sucursal_id": "CENTRO", "franja": f(d, 10), "especialidad": "CARD", "motivo": "Control"}
    llamar("POST", "/citas", json=s | {"expediente": p1}, esperado=201)
    llamar("POST", "/citas", json=s | {"expediente": p2}, esperado=201)
    llamar("POST", "/pacientes", json={"nombre": "Paciente Tres", "telefono": "8100000003"}, esperado=201)
    llamar("POST", "/pacientes", json={"nombre": "Paciente Cuatro", "telefono": "8100000004"}, esperado=201)
    llamar("POST", "/citas", json=s | {"expediente": "EXP-000003"}, esperado=201)
    llamar("POST", "/citas", json=s | {"expediente": "EXP-000004"}, esperado=409)

    paso("4. Aseguradora que exige autorización: queda pendiente (US-12)")
    a = {"medico_id": "MED-001", "sucursal_id": "CENTRO", "franja": f(d, 11), "expediente": p2,
         "aseguradora_id": "SALUDPLUS", "especialidad": "MG"}
    cita_aut = llamar("POST", "/citas", json=a, esperado=201)["cita_id"]
    llamar("POST", f"/citas/{cita_aut}/autorizacion", json={"numero": "AUT-2026-001"}, esperado=200)

    paso("5. Llegada con 14 y 16 minutos de retraso (CU-02, US-08, US-09)")
    llamar("POST", f"/citas/{cita1}/llegada", json={"hora_llegada": datetime.combine(d, time(9, 14)).isoformat()}, esperado=200)
    llamar("POST", f"/citas/{cita_aut}/llegada", json={"hora_llegada": datetime.combine(d, time(11, 16)).isoformat()}, esperado=200)

    paso("6. Cierre de consulta con receta, estudios y nueva cita (US-13)")
    nueva = {"medico_id": "MED-001", "sucursal_id": "CENTRO", "franja": f(d + timedelta(days=1), 9),
             "expediente": p1, "especialidad": "MG", "motivo": "Seguimiento"}
    llamar("POST", f"/citas/{cita1}/cierre", json={"receta": "Paracetamol 500 mg", "estudios": ["Biometría hemática"],
                                                  "nueva_cita": nueva}, esperado=200)

    paso("7. Cancelar con evidencia y auditar (US-17, CU-04)")
    otra = llamar("POST", "/citas", json={"medico_id": "MED-003", "sucursal_id": "SUR", "franja": f(d, 15),
                                         "expediente": p1, "especialidad": "PED"}, esperado=201)["cita_id"]
    llamar("POST", f"/citas/{otra}/cancelar", json={"motivo": "El paciente no puede asistir"}, esperado=200)
    llamar("GET", "/consultas/auditoria", headers=ADM, params={"cita_id": otra}, esperado=200)
    llamar("POST", "/citas", json={"medico_id": "MED-001", "sucursal_id": "CENTRO", "franja": f(d, 10, dur=30),
                                  "expediente": p1, "especialidad": "MG"}, esperado=409)  # ya tiene cita a las 10:00

    paso("8. No-show: se avanza el reloj simulado (CU-05, US-14, US-20)")
    ns = llamar("POST", "/citas", json={"medico_id": "MED-003", "sucursal_id": "SUR", "franja": f(d, 12),
                                       "expediente": "EXP-000003", "especialidad": "PED"}, esperado=201)["cita_id"]
    llamar("POST", f"/citas/{ns}/no-show", esperado=409)
    llamar("PUT", "/demo/reloj", json={"ahora": datetime.combine(d, time(13, 0)).isoformat()})
    llamar("POST", f"/citas/{ns}/no-show", esperado=200)
    llamar("POST", f"/citas/{ns}/no-show", esperado=409)
    llamar("GET", "/consultas/historial-no-shows/EXP-000003", headers=ADM, esperado=200)

    paso("9. El médico cancela su jornada: afectados y reagendado (CU-03, US-11)")
    llamar("PUT", "/demo/reloj", json={"ahora": datetime.combine(d, time(8, 0)).isoformat()})
    c1 = llamar("POST", "/citas", json={"medico_id": "MED-003", "sucursal_id": "SUR", "franja": f(d, 14),
                                       "expediente": p1, "especialidad": "PED"}, esperado=201)["cita_id"]
    llamar("POST", "/citas", json={"medico_id": "MED-003", "sucursal_id": "SUR", "franja": f(d, 13),
                                  "expediente": p2, "especialidad": "PED"}, esperado=201)
    llamar("POST", "/jornadas/cancelar", json={"medico_id": "MED-003", "fecha": str(d), "sucursal_id": "SUR",
                                              "motivo": "Enfermedad del médico"}, esperado=200)
    llamar("GET", "/consultas/citas-afectadas", params={"medico_id": "MED-003", "fecha": str(d)}, esperado=200)
    llamar("PUT", "/demo/reloj", json={"ahora": datetime.combine(d, time(8, 20)).isoformat()})
    llamar("POST", f"/citas/{c1}/reagendar", json={"medico_id": "MED-003", "sucursal_id": "SUR",
                                                  "franja": f(d + timedelta(days=1), 14)}, esperado=201)

    paso("10. Permisos: solo recepción agenda (P3)")
    llamar("POST", "/citas", headers=ADM, json=base | {"expediente": p1}, esperado=403)

    paso("11. Reporte consolidado, con tiempo de reagendado (US-15, US-24)")
    llamar("GET", "/consultas/reporte", headers=ADM, params={"desde": str(d), "hasta": str(d + timedelta(days=1))}, esperado=200)
    llamar("PUT", "/demo/reloj", json={"ahora": None})
    print("\nDemo completa.")


if __name__ == "__main__":
    main()
