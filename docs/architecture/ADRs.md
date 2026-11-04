# Architecture Decision Records

Siete decisiones con consecuencias reales (el curso pide tres como mínimo). ADR-001 a ADR-005 vienen del informe de la Unidad 3 y **pasan de «Propuesta» a «Aceptada»** con la implementación; ADR-006 y ADR-007 se agregan en el PIA. Formato: contexto, alternativas, decisión, consecuencias y trazabilidad.

## ADR-001: Domain Model como patrón de lógica de negocio

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | La agenda tiene invariantes (no duplicar franjas entre sucursales, sobrecupo por médico), un ciclo de estados de la cita y tres canales de entrada. El BRD exige coordinación multi-sucursal en tiempo real. |
| Alternativas | Transaction Script: rápido, pero repite las reglas en cada canal. Table Module: agrupa por tabla, pero las reglas que cruzan médico, jornada y cita quedan sueltas. |
| Decisión | Domain Model para agenda y cita. Transaction Script solo para pacientes, catálogos y consultas, donde casi no hay reglas. |
| Consecuencias | Las reglas viven en un solo lugar y se prueban sin base de datos (50+ pruebas unitarias de dominio). Cuesta más diseño inicial y un mapeo a la base de datos. Si el negocio recortara el alcance a una agenda sin sobrecupo ni autorizaciones, habría que reconsiderarla. |
| Trazabilidad | BRD N1/N5; US-04, 05, 10, 12; CU-01, CU-02; `src/domain/` |

## ADR-002: AgendaMedica por médico y fecha como Aggregate raíz, con versión optimista

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | Hay médicos que atienden en dos sucursales y ahí se duplican citas (P11). La regla debe cumplirse aunque dos recepcionistas agenden al mismo tiempo. |
| Alternativas | Cita como Aggregate propio con restricción única en la BD: deja la regla en infraestructura y no expresa el sobrecupo variable. Una agenda por sucursal: no ve al médico en otra sucursal. Una agenda por médico con todo su historial: demasiado grande. Bloqueo pesimista (SELECT FOR UPDATE): serializa y no funciona igual en memoria. |
| Decisión | Un Aggregate por médico y fecha que abarca todas las sucursales, con columna `version`. El guardado hace `UPDATE … WHERE version = v`; si afecta 0 filas (o el INSERT choca con la llave primaria) se lanza `ConflictoDeVersion`, que el servicio traduce en `HorarioNoDisponible`. |
| Consecuencias | La franja y el sobrecupo se protegen en un solo objeto y la concurrencia se resuelve sin bloqueos largos. Reagendar entre fechas toca dos agendas y requiere el `Reagendador` dentro de una sola Unit of Work. Se verifica con T6 sobre PostgreSQL. |
| Trazabilidad | US-05, US-10, US-16; P7, P11; CU-01, CU-03; `agenda_medica.py`, `repositorios_sql.py` |

## ADR-003: Auditoría mediante Domain Events dentro de la misma transacción

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | El BRD pide que el 100 % de cancelaciones y modificaciones tenga usuario, fecha y motivo (P16). |
| Alternativas | Auditoría asíncrona: podría perderse si falla. Que cada servicio la escriba a mano: se olvida en algún caso de uso. |
| Decisión | Los eventos `CitaCancelada`, `CitaModificada`, `CitaAfectadaPorJornada` y `CitaReagendada` generan un `RegistroDeAuditoria` en `UnitOfWork.confirmar()` **antes** del commit. Las notificaciones se envían **después** de confirmar y, si fallan, no deshacen la cita. |
| Consecuencias | No puede existir una cancelación sin su registro (T5). La transacción es algo más larga y la auditoría depende de que el dominio emita el evento, por lo que cada operación auditable tiene su prueba. |
| Trazabilidad | US-17, US-19; CU-04; `unit_of_work.py` |

## ADR-004: CQRS básico con una sola base de datos

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | La pantalla de disponibilidad junta las tres sucursales y los reportes agrupan por sucursal y médico; no se parecen al modelo que protege las reglas. |
| Alternativas | Leer cargando Aggregates: lento y acopla las pantallas al dominio. CQRS completo con bases separadas: complejidad que ~35 médicos y 3 sucursales no justifican. |
| Decisión | Commands por el dominio (Service Layer) y Queries por `LectorSql` con View Models propios, sobre la misma base de datos. |
| Consecuencias | Las consultas no cargan agendas ni abren transacciones de escritura. Hay dos caminos que mantener y el riesgo de que un lector repita una regla; se evita no poniendo lógica de negocio en los lectores. |
| Trazabilidad | US-01, 11, 14, 15, 16; `lectores_sql.py`, `consultas.py` |

## ADR-005: Políticas por interfaz para reglas que el negocio no ha definido o que varían

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | La política de no-shows la debe aprobar la dirección (P10) y las aseguradoras piden cosas distintas (P9). |
| Alternativas | Fijar un umbral supuesto dentro de la cita: inventa una regla. Un condicional por aseguradora: crece con cada convenio. |
| Decisión | Interfaces `PoliticaDeNoShow` y `PoliticaDeAutorizacion` (patrón Strategy). Implementaciones: `AlertaPorUmbralDeNoShows` (decisión D3: alerta con 3 o más, configurable, **no bloquea**), `SinSancionPorNoShow` y `AutorizacionPorCatalogo`. |
| Consecuencias | Dirección puede cambiar la política sin tocar los casos de uso. Mientras no la apruebe, el sistema solo advierte. El umbral queda como supuesto documentado, no como regla fija. |
| Trazabilidad | P9, P10; US-12, US-14, US-20; CU-05; `politicas.py` |

## ADR-006: Specification y State Machine para las reglas y el ciclo de la cita

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | El PIA exige Specification y State Machine. Las reglas de agendado (franja dentro de jornada, libre o sobrecupo, paciente sin cita traslapada) se combinan de varias formas y el estatus de la cita tiene 9 estados con transiciones restringidas. |
| Alternativas | `if` anidados dentro de `AgendaMedica`: ilegibles y difíciles de probar por separado. Un campo `estatus` libre: cualquier código podría saltarse una transición. Librería externa de máquinas de estado: dependencia sin necesidad. |
| Decisión | `Especificacion[T]` con `&`, `|` y `~` y especificaciones pequeñas (`HorarioLibre | SobrecupoDisponible`). `MaquinaDeEstadosDeCita` con una **tabla única** de transiciones (estado, disparador → estado) de la que se genera el diagrama. |
| Consecuencias | Cada regla del BRD se prueba aislada y se compone. Una transición no declarada es imposible (prueba que recorre todas las combinaciones). Más clases pequeñas que un diseño con condicionales. |
| Trazabilidad | US-05, 07, 09, 10, 12, 20; `especificaciones.py`, `estados.py` |

## ADR-007: FastAPI + SQLAlchemy + PostgreSQL, configuración 12-Factor y Docker Compose

| Campo | Contenido |
|---|---|
| Estado | **Aceptada** |
| Contexto | El PIA exige API REST documentada con Swagger/OpenAPI, persistencia, configuración por variables de entorno, Docker Compose (DB + App + Tests) y despliegue. |
| Alternativas | Flask/Django REST: sin OpenAPI generado de los tipos (Flask) o más pesado que el caso (Django). ORM completo con el dominio mapeado directamente: acoplaría el dominio a SQLAlchemy. SQLite en producción: no demuestra la concurrencia. |
| Decisión | FastAPI (OpenAPI 3.1 y Swagger UI servido localmente sin CDN), SQLAlchemy 2 solo en `infrastructure/` con mapeo manual fila↔dominio, PostgreSQL 16 en Compose, `DATABASE_URL` y demás parámetros por entorno, SQLite en memoria para pruebas rápidas y PostgreSQL en CI. Despliegue con `render.yaml` + job de GitHub Actions. |
| Consecuencias | El dominio no importa FastAPI ni SQLAlchemy (lo verifica una prueba). Mapeo manual implica más código que un ORM declarativo sobre el dominio. `create_all` al arrancar sustituye a migraciones; con datos productivos reales habría que adoptar Alembic. |
| Trazabilidad | Requisitos 3–5 del PIA; `docker-compose.yml`, `Dockerfile`, `.github/workflows/ci.yml` |
