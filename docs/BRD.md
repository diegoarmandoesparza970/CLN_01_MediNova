# BRD — MediNova: sistema de gestión de citas multi-sucursal

**Versión final (PIA)** · Equipo 1 · Componentes de Lógica de Negocio · Refinado a partir de Actividad 2 (U2) y el informe de arquitectura (U3).

| Integrante | Matrícula |
|---|---|
| Diego Armando Esparza Flores | 1908457 |
| Cristopher Led Juarez Luna | 2019069 |
| José Ángel Leal Sifuentes | 2025292 |

## 1. Contexto
MediNova es una clínica privada con **tres sucursales** y alrededor de **35 médicos** (empleados y por honorarios, con horarios que cambian cada semana). Ingresa por consultas de medicina general, especialidades, estudios básicos y procedimientos menores. Los pacientes pagan de forma particular o mediante convenios con aseguradoras. Las citas se piden por **teléfono, WhatsApp o en recepción** y hoy se gestionan en una agenda compartida operada manualmente.

## 2. Problema / oportunidad
1. Citas duplicadas entre sucursales por falta de validación centralizada de horarios (**prioridad #1** según el stakeholder).
2. Poca visibilidad de la disponibilidad de un mismo médico entre las tres sucursales.
3. Cancelaciones sin evidencia de quién las hizo y por qué.
4. Dificultad para medir no-shows y construir un historial confiable por paciente.

## 3. Stakeholders
| Stakeholder | Interés | Interacción con el sistema |
|---|---|---|
| Paciente | Solicitar, confirmar y asistir | Indirecta (recibe confirmaciones por su canal) |
| Recepcionista | Agendar, confirmar, reagendar | Usuario principal; **única** que agenda y cancela |
| Médico | Define disponibilidad, atiende, indica sobrecupo | **No usa el sistema** (entrevista P3/P4): avisa a recepción, que captura |
| Personal administrativo | Políticas de no-show y autorizaciones, reportes | Consulta historial, auditoría y reportes |
| Aseguradora | Valida cobertura y autoriza | Externa; su autorización la registra recepción |
| Dirección de MediNova | Patrocinador; define prioridades y mide el éxito | Reportes consolidados |

## 4. Alcance
**Dentro:** solicitud y agendamiento por los tres canales, disponibilidad multi-sucursal, confirmación previa y liberación de horario sin respuesta, registro de llegada y retrasos, sobrecupo por médico, cancelación/modificación con auditoría, no-shows e historial, cancelación de jornada y reagendado, registro de autorización de aseguradora, cierre de consulta (receta/estudios/nueva cita) y reportes básicos.
**Fuera:** expediente clínico completo, integración directa con sistemas de aseguradoras, marketing, autenticación corporativa (SSO) e integración real con WhatsApp Business (queda como adaptador).

## 5. Necesidades del negocio
| ID | Necesidad | US |
|---|---|---|
| N1 | Evitar citas duplicadas de un médico entre sucursales | US-04, US-05 |
| N2 | Consultar la disponibilidad de un médico en las tres sucursales desde un solo lugar | US-01, US-16 |
| N3 | Dejar evidencia de cada cambio o cancelación | US-17, US-19 |
| N4 | Construir un historial de no-shows por paciente | US-14, US-20 |
| N5 | Controlar el sobrecupo permitido por cada médico | US-10 |
| N6 | Reducir el trabajo manual al reagendar cuando un médico cancela su jornada | US-09, US-11, US-23, US-24 |
| N7 | Registrar cuándo una aseguradora requiere autorización previa | US-12 |
| N8 | Registrar llegadas y retrasos con tolerancia | US-07, US-08, US-09 |
| N9 | Confirmar por el canal de origen y liberar horarios sin respuesta | US-06, US-18, US-21 |
| N10 | Alta y búsqueda de pacientes sin duplicados; datos al día | US-02, US-03, US-22 |
| N11 | Reportes por sucursal y médico | US-15, US-24 |
| N12 | Cierre de consulta | US-13 |

## 6. Restricciones
- Los horarios de los médicos cambian cada semana (las jornadas se abren por fecha).
- Se mantienen los tres canales: teléfono, WhatsApp y presencial.
- Operación multi-sucursal coordinada en tiempo real (control de concurrencia, ADR-002).
- No existe política uniforme de no-shows; cualquier regla nueva requiere aprobación de dirección.

## 7. Supuestos refinados y decisiones del equipo
En la Unidad 2 los supuestos estaban «pendientes de validar». Para el PIA el equipo tomó las siguientes decisiones; cada una es **configurable o aislada** para poder cambiarla sin tocar los casos de uso.

| ID | Tema abierto en U2/U3 | Decisión del equipo | Dónde vive |
|---|---|---|---|
| D1 | ¿Los médicos usan el sistema? | No. Recepción captura lo que indica el médico (sobrecupo, cierre de consulta, cancelación de jornada). | Roles de la API |
| D2 | Meta de −40 % de no-shows (no sale del caso) | Es un **indicador objetivo**, no una regla: el reporte calcula la tasa de no-show para medir la línea base. | `ObtenerReporteConsolidado` |
| D3 | Política de no-shows sin definir (P10) | Estrategia `AlertaPorUmbralDeNoShows`: con **3 o más** no-shows recepción recibe una alerta para reforzar la confirmación. **No bloquea** al paciente. Umbral configurable (`NOSHOW_UMBRAL`) y **sujeto a aprobación de dirección**; `SinSancionPorNoShow` está disponible. | `domain/politicas.py` |
| D4 | ¿Se cancela una sola jornada si el médico atiende en dos sucursales? | Sí: se cancela la jornada de **una sucursal** o, si no se indica, **todas** las del día. | `AgendaMedica.cancelar_jornada` |
| D5 | Autorización de la aseguradora (síncrona o asíncrona) | Es un Value Object de la cita. Sin número la cita queda `pendiente_autorizacion` (**bloquea la franja**) y se registra después. Con autorización pendiente **no se registra llegada**: recepción registra el número, cobra como particular (`pago-particular`) o reagenda (Q13). Si faltan menos horas que la anticipación de la aseguradora (p. ej. 48 h) se **advierte**, no se bloquea. | `Cita`, `PoliticaDeAutorizacion` |
| D6 | Orden para reagendar al cancelar la jornada (P12: práctica sin regla escrita) | Se formaliza: **la cita más próxima primero**. | `cancelar_jornada`, `LectorSql.citas_afectadas` |
| D7 | Liberar horario si no se confirma (Q6: «nos gustaría») | Si pasan **24 h** desde el recordatorio sin respuesta, el horario se libera, con auditoría a nombre de `sistema`. Una respuesta *rechazada* libera de inmediato. | `ConfirmacionService` |
| D8 | Paciente que agenda en dos sucursales y no llega a ninguna (Q8) | Un paciente **no puede tener dos citas que se traslapen**. No se fija un máximo de citas activas. | `PacienteSinCitaSolapada` |
| D9 | Duración de las citas | Franjas de **30 min** configurables (`DURACION_CITA_MINUTOS`); horas locales de la clínica (`America/Monterrey`). | Configuración |
| D10 | Tolerancia en las tres sucursales | **15 minutos** igual en las tres, configurable (`TOLERANCIA_MINUTOS`). | `Tolerancia` |
| D11 | Límite de sobrecupo | Es un dato del médico (0 = no acepta) que recepción captura; la regla es una sola. | `Medico`, `SobrecupoDisponible` |
| D12 | Autenticación | Fuera de alcance: rol y usuario llegan en cabeceras `X-Rol`/`X-Usuario` y se usan para autorizar y auditar. | `api/seguridad.py` |
| D13 | WhatsApp | Adaptador **simulado** (registra en una bandeja); la API real requiere credenciales de la clínica. Teléfono y recepción quedan «pendiente de gestión manual». | `NotificadorPorCanal` |
| D14 | Estados de la cita | Se agregan `pendiente_autorizacion`, `afectada` y `reagendada` a los del informe; transiciones en una tabla única (State Machine). | `domain/estados.py` |

## 8. Criterios de éxito (y cómo se miden en el sistema)
| Criterio | Medición |
|---|---|
| Reducción medible de citas duplicadas entre sucursales | Imposible por diseño: invariante de `AgendaMedica` + versión optimista; pruebas T1 y T6 |
| Reducción del 40 % de no-shows respecto a la línea base | `tasa_no_show_pct` del reporte, comparando periodos (la línea base la aporta MediNova) |
| 100 % de cancelaciones/modificaciones con usuario, fecha, hora y motivo | Auditoría en la misma transacción (ADR-003); prueba T5 |
| Menor tiempo de reagendado al cancelar una jornada | `tiempo_promedio_reagendado_min` del reporte (US-24) |

## 9. Trazabilidad
Ver [`analisis/trazabilidad.md`](analisis/trazabilidad.md) (necesidad → US → caso de uso → regla → dominio/código → prueba → ADR) y la matriz generada [`analisis/trazabilidad-pruebas.md`](analisis/trazabilidad-pruebas.md).
