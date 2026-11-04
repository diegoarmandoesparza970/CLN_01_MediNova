from __future__ import annotations

from fastapi import Request

from .composicion import Contenedor


def contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor
