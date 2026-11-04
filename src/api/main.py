"""Punto de entrada FastAPI. Swagger UI en /docs, OpenAPI en /openapi.json."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.domain import errores as err
from src.infrastructure import db
from src.infrastructure.config import Configuracion
from src.infrastructure.seed import cargar_demo

from .composicion import Contenedor, construir
from .esquemas import RelojIn
from .routers import catalogos, citas, consultas, jornadas, pacientes

DESCRIPCION = """
API de **MediNova** (3 sucursales, ~35 médicos): agendar sin duplicados entre sucursales, controlar
sobrecupo, registrar llegadas con tolerancia de 15 min, cancelar jornadas y reagendar, auditar cambios
y medir no-shows.

**Cómo probar:** pulse *Authorize* y capture `X-Usuario` (p. ej. `maria`) y `X-Rol`
(`recepcion`, `administrativo` o `direccion`). Solo `recepcion` agenda y cancela (entrevista, P3).
"""

HTTP_POR_ERROR: list[tuple[type, int]] = [
    (err.PermisoDenegado, 403),
    (err.NoEncontrado, 404),
    (err.HorarioNoDisponible, 409), (err.SobrecupoExcedido, 409), (err.ConflictoDeVersion, 409),
    (err.TransicionDeEstatusInvalida, 409), (err.PacienteDuplicado, 409),
    (err.CitaSolapadaDelPaciente, 409), (err.JornadaTraslapada, 409),
    (err.FranjaFueraDeJornada, 422), (err.DatosInvalidos, 422),
]


def crear_app(config: Configuracion | None = None, contenedor: Contenedor | None = None) -> FastAPI:
    config = config or Configuracion.desde_entorno()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.contenedor = contenedor or construir(config)
        db.crear_esquema(app.state.contenedor.engine)
        if config.seed_demo:
            cargar_demo(app.state.contenedor)
        yield
        if contenedor is None:
            app.state.contenedor.engine.dispose()

    app = FastAPI(title="MediNova API", version="1.0.0", description=DESCRIPCION, lifespan=lifespan,
                  contact={"name": "Equipo CLN · MediNova"}, docs_url=None)

    # Swagger UI se sirve desde la propia app (sin CDN): la demo funciona sin internet.
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
    def swagger_ui():
        return get_swagger_ui_html(
            openapi_url="/openapi.json", title="MediNova API - Swagger UI",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
            swagger_favicon_url="/static/swagger/favicon-32x32.png",
            swagger_ui_parameters={"docExpansion": "list", "persistAuthorization": True})

    @app.exception_handler(err.ErrorDeDominio)
    async def _dominio(_: Request, ex: err.ErrorDeDominio):
        status = next((s for tipo, s in HTTP_POR_ERROR if isinstance(ex, tipo)), 400)
        cuerpo = {"codigo": ex.codigo, "mensaje": str(ex)}
        if isinstance(ex, err.PacienteDuplicado):
            cuerpo["expediente"] = ex.expediente
        return JSONResponse(cuerpo, status_code=status)

    @app.exception_handler(HTTPException)
    async def _http(_: Request, ex: HTTPException):
        cuerpo = ex.detail if isinstance(ex.detail, dict) else {"codigo": "error_http", "mensaje": str(ex.detail)}
        return JSONResponse(cuerpo, status_code=ex.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, ex: RequestValidationError):
        detalle = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in ex.errors())
        return JSONResponse({"codigo": "datos_invalidos", "mensaje": detalle}, status_code=422)

    for r in (catalogos.router, pacientes.router, jornadas.router, citas.router, consultas.router):
        app.include_router(r)

    @app.get("/health", tags=["Operación"], summary="Estado del servicio y la base de datos")
    def health(request: Request):
        from sqlalchemy import text
        c: Contenedor = request.app.state.contenedor
        with c.session_factory() as s:
            s.execute(text("SELECT 1"))
        return {"estado": "ok", "entorno": c.config.app_env}

    if config.reloj_simulable:  # solo demostraciones: permite probar retrasos y no-shows sin esperar
        @app.put("/demo/reloj", tags=["Demo"], summary="Fijar la hora simulada (null = hora real)")
        def fijar_reloj(body: RelojIn, request: Request):
            r = request.app.state.contenedor.reloj
            r.fijar(body.ahora)
            return {"ahora": r.ahora().isoformat()}

        @app.get("/demo/reloj", tags=["Demo"], summary="Hora que usa el sistema")
        def ver_reloj(request: Request):
            return {"ahora": request.app.state.contenedor.reloj.ahora().isoformat()}

    @app.get("/", include_in_schema=False)
    def raiz():
        return RedirectResponse("/docs")

    return app


app = crear_app()
