"""Identidad y permisos del caso de uso (informe, sección 4: «solo recepción agenda y cancela»).

La autenticación real (SSO/JWT) queda fuera del alcance del BRD; aquí el rol y el usuario
llegan por cabeceras y se usan para autorizar y para la auditoría (usuario de cada cambio).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

_usuario = APIKeyHeader(name="X-Usuario", scheme_name="Usuario", auto_error=False, description="Usuario que opera (se audita)")
_rol = APIKeyHeader(name="X-Rol", scheme_name="Rol", auto_error=False,
                    description="recepcion | administrativo | direccion")


class Rol(str, Enum):
    RECEPCION = "recepcion"
    ADMINISTRATIVO = "administrativo"
    DIRECCION = "direccion"


@dataclass(frozen=True)
class Identidad:
    usuario: str
    rol: Rol


def identidad(usuario: str | None = Depends(_usuario), rol: str | None = Depends(_rol)) -> Identidad:
    if not usuario or not rol:
        raise HTTPException(401, {"codigo": "no_autenticado", "mensaje": "Faltan las cabeceras X-Usuario y X-Rol"})
    try:
        return Identidad(usuario.strip(), Rol(rol.strip().lower()))
    except ValueError:
        raise HTTPException(401, {"codigo": "rol_invalido",
                                  "mensaje": "X-Rol debe ser recepcion, administrativo o direccion"}) from None


def requiere(*roles: Rol):
    def dependencia(ident: Identidad = Depends(identidad)) -> Identidad:
        if ident.rol not in roles:
            raise HTTPException(403, {"codigo": "permiso_denegado",
                                      "mensaje": f"El rol '{ident.rol.value}' no puede realizar esta operación"})
        return ident
    return dependencia


SOLO_RECEPCION = requiere(Rol.RECEPCION)
CUALQUIER_ROL = requiere(Rol.RECEPCION, Rol.ADMINISTRATIVO, Rol.DIRECCION)
GESTION = requiere(Rol.RECEPCION, Rol.ADMINISTRATIVO)
ANALISIS = requiere(Rol.ADMINISTRATIVO, Rol.DIRECCION)
