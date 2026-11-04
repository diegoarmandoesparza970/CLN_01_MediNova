# MediNova — gestión de citas multi-sucursal

Proyecto Integrador de Aprendizaje · Componentes de Lógica de Negocio (CLN) · Equipo 1
Caso asignado: **MediNova**, clínica con 3 sucursales y ~35 médicos (la misma empresa de las Unidades 2 y 3).

| | |
|---|---|
| Repositorio | https://github.com/Crisled/CLN_01_MediNova |
| Sistema desplegado (Swagger UI) | `https://<COMPLETAR-URL-DE-RENDER>.onrender.com/docs` ← pegar aquí la URL tras desplegar (ver «Despliegue») |
| Integrantes | Diego Armando Esparza Flores (1908457) · Cristopher Led Juarez Luna (2019069) · José Ángel Leal Sifuentes (2025292) |

## Qué hace
Agenda citas **sin duplicados entre sucursales**, controla el sobrecupo de cada médico, registra llegadas con tolerancia de 15 minutos, maneja autorizaciones de aseguradoras, cancela jornadas y reagenda a los afectados, deja **auditoría de cada cambio** y mide no-shows. Implementa **DDD, Specification, State Machine y una API REST documentada (OpenAPI/Swagger)** sobre PostgreSQL.

![estados](docs/architecture/diagramas/estados-cita.png)

## Estructura
```
CLN_01_MediNova/
├── docs/
│   ├── BRD.md                      BRD refinado + decisiones del equipo
│   ├── analisis/                   user-stories.md (24, Gherkin), bpmn.md, glosario.md, trazabilidad*.md
│   ├── architecture/               ADRs.md (7), decisiones-tecnicas.md, diagramas/ (.mmd + .png)
│   ├── api/openapi.json            especificación OpenAPI exportada
│   └── evidencias/                 capturas y salida de la demo
├── src/
│   ├── domain/                     Aggregates, entidades, VO, eventos, Specification, State Machine, políticas
│   ├── application/                Service Layer, Commands/Queries, puertos
│   ├── infrastructure/             SQLAlchemy (repositorios, UoW, lectores), reloj, notificador, config
│   └── api/                        FastAPI: routers, esquemas, seguridad, composición
├── tests/                          unit/ (dominio) + integration/ (SQL y API) + trazabilidad
├── scripts/                        demo_api.py, exportar_openapi.py, trazabilidad.py
├── .github/workflows/ci.yml        CI/CD
├── docker-compose.yml  Dockerfile  render.yaml
├── .env.example                    sin secretos reales
└── README.md
```

## Ejecución con Docker Compose (recomendada)
```bash
cp .env.example .env                       # ajuste la contraseña de la BD
docker compose up --build -d db app        # PostgreSQL + API
# Swagger UI:  http://localhost:8000/docs      Salud: http://localhost:8000/health
docker compose --profile test run --rm tests   # suite completa sobre PostgreSQL con cobertura >= 80 %
docker compose down -v
```
Con `SEED_DEMO=true` se cargan 3 sucursales, 3 médicos, 2 aseguradoras y 2 pacientes ficticios.

## Ejecución local (sin Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn src.api.main:app --reload          # usa SQLite (medinova.db) si no hay DATABASE_URL
# con PostgreSQL: DATABASE_URL=postgresql://usuario:clave@localhost:5432/medinova
```

## Pruebas y cobertura
```bash
pytest --cov --cov-fail-under=80                                   # SQLite en memoria
TEST_DATABASE_URL=postgresql+psycopg2://u:p@localhost:5432/medinova_test pytest   # PostgreSQL
ruff check src tests scripts
python -m scripts.trazabilidad --escribir                          # matriz requisito -> prueba
```
132 pruebas (unitarias de dominio + integración sobre BD real + API + paquete de datos CSV del PIA), **cobertura 99 %**. Las pruebas T1–T8 del informe de la Unidad 3 están implementadas; cada prueba declara las US/CU/ADR que verifica con `@pytest.mark.traza(...)` y una prueba falla si alguna US-01…24 queda sin cubrir.

Los CSV del PIA (`tests/datos_csv/`: 120 casos y 20 transiciones) se ejecutan con `python -m scripts.ejecutar_csv` y en `tests/integration/test_datos_csv.py`; ver `docs/analisis/pruebas-csv.md`.

## Cómo usar la API
En Swagger UI pulse **Authorize** y capture `X-Usuario` (p. ej. `maria`) y `X-Rol`:
`recepcion` (agenda, cancela, registra llegadas), `administrativo` (historial, reportes, auditoría) o `direccion` (reportes).

## Demostración en vivo
```bash
# servidor con RELOJ_SIMULABLE=true (ya está en .env.example) para simular horas sin esperar
BASE_URL=http://localhost:8000 python -m scripts.demo_api
```
Recorre: disponibilidad en dos sucursales → duplicado rechazado (409) → sobrecupo → autorización pendiente → llegada con 14 y 16 min → cierre con nueva cita → cancelación con auditoría → no-show → jornada cancelada y reagendado → permisos → reporte. La salida de una ejecución real está en `docs/evidencias/demo_salida.txt`.

## Despliegue (Render, Railway o Fly.io)
1. Suba el repositorio a GitHub y conecte Render con *New → Blueprint* (usa `render.yaml`: PostgreSQL + servicio web Docker).
2. En el servicio cree el *Deploy Hook* y guárdelo como secret `RENDER_DEPLOY_HOOK_URL` en GitHub: el job `deploy` de `.github/workflows/ci.yml` lo dispara tras pasar pruebas e imagen.
3. Verifique `https://<su-servicio>.onrender.com/health` y `/docs`, y pegue la URL en la tabla de arriba.
4. Para la demostración deje `SEED_DEMO=true`; para producción real, `SEED_DEMO=false` y `RELOJ_SIMULABLE=false`.

## Variables de entorno
Ver `.env.example`. Las reglas del negocio (tolerancia, duración de franja, umbral de no-shows, horas para liberar sin confirmar) son configurables sin tocar el código.

## Decisiones y límites
- Decisiones del equipo sobre lo que el análisis dejó abierto: `docs/BRD.md` §7 (D1–D14).
- WhatsApp es un adaptador **simulado**; no hay autenticación corporativa ni migraciones Alembic (`create_all` al arrancar). Ver `docs/architecture/decisiones-tecnicas.md` §6.
