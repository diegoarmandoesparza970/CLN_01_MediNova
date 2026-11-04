"""Modelo mínimo del paquete CSV: operaciones con líneas, Specifications y máquina de estados."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path

from src.domain.errores import ErrorDeDominio, TransicionDeEstatusInvalida
from src.domain.especificaciones import Especificacion

DATOS = Path(__file__).resolve().parent.parent / "datos_csv"
UMBRAL_BENEFICIO = Decimal("1500")


# ---------------------------------------------------------------- datos
@dataclass(frozen=True)
class Actor:
    id: str
    nombre: str
    es_preferente: bool
    activo: bool
    ciudad: str


@dataclass(frozen=True)
class Recurso:
    id: str
    descripcion: str
    precio: Decimal
    capacidad: int
    habilitado: bool


@dataclass(frozen=True)
class Linea:
    recurso: Recurso
    cantidad: int

    @property
    def importe(self) -> Decimal:
        return self.recurso.precio * self.cantidad


class EstadoOperacion(str, Enum):
    SOLICITADA = "SOLICITADA"
    CONFIRMADA = "CONFIRMADA"
    ATENDIDA = "ATENDIDA"
    CANCELADA = "CANCELADA"


class PrecondicionNoCumplida(ErrorDeDominio):
    codigo = "precondicion_no_cumplida"


@dataclass(frozen=True)
class Evento:
    nombre: str
    operacion_id: str


# Única tabla de transiciones (misma idea que MaquinaDeEstadosDeCita).
E = EstadoOperacion
TRANSICIONES = {
    (E.SOLICITADA, "aprobar"): E.CONFIRMADA,
    (E.CONFIRMADA, "atender"): E.ATENDIDA,
    (E.SOLICITADA, "cancelar"): E.CANCELADA,
    (E.CONFIRMADA, "cancelar"): E.CANCELADA,
}
EVENTO_DE = {"aprobar": "OperacionConfirmada", "atender": "OperacionAtendida", "cancelar": "OperacionCancelada"}


@dataclass
class Operacion:
    id: str
    actor: Actor
    estado: EstadoOperacion
    fecha_solicitud: str
    promocion_activa: bool
    autorizado: bool
    lineas: list[Linea] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((ln.importe for ln in self.lineas), Decimal("0"))

    def _transicionar(self, accion: str) -> None:
        destino = TRANSICIONES.get((self.estado, accion))
        if destino is None:
            raise TransicionDeEstatusInvalida(f"No se puede '{accion}' desde {self.estado.value}")
        self.estado = destino
        self.eventos.append(Evento(EVENTO_DE[accion], self.id))

    def aprobar(self) -> None:
        if not PUEDE_PROCESARSE.es_satisfecha_por(self):
            raise PrecondicionNoCumplida("La operación no cumple puede_procesarse")
        self._transicionar("aprobar")

    def atender(self) -> None:
        self._transicionar("atender")

    def cancelar(self) -> None:
        self._transicionar("cancelar")


# ---------------------------------------------------------------- specifications
class ActorActivo(Especificacion[Operacion]):
    def es_satisfecha_por(self, o):
        return o.actor.activo


class DetalleNoVacio(Especificacion[Operacion]):
    def es_satisfecha_por(self, o):
        return len(o.lineas) > 0


class OperacionAutorizada(Especificacion[Operacion]):
    def es_satisfecha_por(self, o):
        return o.autorizado


class ActorPreferente(Especificacion[Operacion]):
    def es_satisfecha_por(self, o):
        return o.actor.es_preferente


class TotalMinimo(Especificacion[Operacion]):
    def __init__(self, minimo: Decimal = UMBRAL_BENEFICIO):
        self.minimo = minimo

    def es_satisfecha_por(self, o):
        return o.total >= self.minimo


class PromocionActiva(Especificacion[Operacion]):
    def es_satisfecha_por(self, o):
        return o.promocion_activa


class LineasValidas(Especificacion[Operacion]):
    """Cantidad > 0, dentro de la capacidad/stock y recurso habilitado."""

    def es_satisfecha_por(self, o):
        return all(ln.cantidad > 0 and ln.cantidad <= ln.recurso.capacidad and ln.recurso.habilitado for ln in o.lineas)


PUEDE_PROCESARSE = ActorActivo() & DetalleNoVacio() & OperacionAutorizada()
BENEFICIO_REFERENCIA = ActorPreferente() & TotalMinimo() & ~PromocionActiva()
OPERACION_COMPLETAMENTE_VALIDA = PUEDE_PROCESARSE & LineasValidas()


# ---------------------------------------------------------------- carga
def _leer(nombre: str) -> list[dict]:
    with open(DATOS / nombre, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cargar() -> dict:
    actores = {r["actor_id"]: Actor(r["actor_id"], r["nombre"], r["es_preferente"] == "1", r["activo"] == "1", r["ciudad"])
               for r in _leer("actores.csv")}
    recursos = {r["recurso_id"]: Recurso(r["recurso_id"], r["descripcion"], Decimal(r["precio_mxn"]),
                                         int(r["capacidad_o_stock"]), r["habilitado"] == "1")
                for r in _leer("catalogo.csv")}
    ops = {}
    for r in _leer("operaciones.csv"):
        ops[r["operacion_id"]] = Operacion(r["operacion_id"], actores[r["actor_id"]], EstadoOperacion(r["estado_inicial"]),
                                           r["fecha_solicitud"], r["promocion_activa"] == "1", r["autorizado"] == "1")
    for r in _leer("detalle_operaciones.csv"):
        ops[r["operacion_id"]].lineas.append(Linea(recursos[r["recurso_id"]], int(r["cantidad"])))
    return {"actores": actores, "recursos": recursos, "operaciones": ops,
            "casos": _leer("casos_prueba.csv"), "transiciones": _leer("transiciones_prueba.csv"),
            "detalle": _leer("detalle_operaciones.csv")}


# ---------------------------------------------------------------- ejecución
def ejecutar_caso(caso: dict, op: Operacion) -> tuple[str, str]:
    """Devuelve (resultado, evidencia) para una fila de casos_prueba.csv."""
    if caso["tipo_prueba"] == "validar_operacion":
        ok = PUEDE_PROCESARSE.es_satisfecha_por(op)
        ev = f"actor_activo={int(op.actor.activo)}; lineas={len(op.lineas)}; autorizado={int(op.autorizado)}"
    else:
        ok = BENEFICIO_REFERENCIA.es_satisfecha_por(op)
        ev = f"preferente={int(op.actor.es_preferente)}; total={op.total:.2f}; promocion={int(op.promocion_activa)}"
    return ("CUMPLE" if ok else "NO_CUMPLE"), ev


def ejecutar_transicion(caso: dict, op: Operacion) -> tuple[str, str]:
    """Devuelve (estado_final, evento_o_excepcion) para una fila de transiciones_prueba.csv."""
    accion = caso["accion_sugerida"]
    try:
        if accion == "aprobar":
            op.aprobar()
        elif accion == "completar":
            op.aprobar()
            op.atender()
        elif accion == "cancelar":
            op.cancelar()
        elif accion == "repetir_aprobacion":
            op.aprobar()
            op.aprobar()
        elif accion == "saltar_estado":
            op.atender()  # SOLICITADA -> ATENDIDA sin pasar por CONFIRMADA
        else:
            raise ValueError(accion)
        resumen = " + ".join(e.nombre for e in op.eventos)
    except ErrorDeDominio as e:
        resumen = f"EXCEPCION {e.codigo}"
        if op.eventos:
            resumen = " + ".join(e_.nombre for e_ in op.eventos) + " | " + resumen
    return op.estado.value, resumen


def ejecutar_todo() -> dict:
    d = cargar()
    res_casos = []
    for c in d["casos"]:
        r, ev = ejecutar_caso(c, d["operaciones"][c["operacion_id"]])
        res_casos.append({**c, "resultado_alumno": r, "evidencia": ev})
    # las transiciones corren sobre copias frescas (estado SOLICITADA y sin eventos)
    d2 = cargar()
    res_trans = []
    for t in d2["transiciones"]:
        estado, ev = ejecutar_transicion(t, d2["operaciones"][t["operacion_id"]])
        res_trans.append({**t, "resultado_alumno": estado, "evidencia": ev})
    return {"datos": d, "casos": res_casos, "transiciones": res_trans}


def escribir_resultados(destino: Path) -> dict:
    r = ejecutar_todo()
    destino.mkdir(parents=True, exist_ok=True)
    for clave, nombre, campos in (
        ("casos", "resultados_casos_prueba.csv", ["caso_id", "operacion_id", "tipo_prueba", "regla_a_verificar", "resultado_alumno", "evidencia"]),
        ("transiciones", "resultados_transiciones.csv", ["caso_id", "operacion_id", "accion_sugerida", "estado_inicial", "resultado_alumno", "evidencia"]),
    ):
        with open(destino / nombre, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            w.writerows(r[clave])
    return r
