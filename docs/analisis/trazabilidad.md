# Matriz de trazabilidad: BRD → US → caso de uso → regla → código → prueba → ADR

La matriz se **verifica automáticamente**: `tests/test_trazabilidad.py` falla si alguna US-01…US-24, CU-01…CU-05 o ADR-001…ADR-007 no tiene al menos una prueba marcada con `@pytest.mark.traza(...)`. La versión generada con los nombres de las pruebas está en [`trazabilidad-pruebas.md`](trazabilidad-pruebas.md) (`python -m scripts.trazabilidad --escribir`).

| Necesidad del BRD | US | CU | Regla de negocio | Dominio / aplicación / API | Pruebas | ADR |
|---|---|---|---|---|---|---|
| N1 Evitar citas duplicadas entre sucursales | US-04, US-05 | CU-01 | Una cita por franja del médico en cualquier sucursal, salvo sobrecupo | `AgendaMedica.agendar`, `HorarioLibre`, versión optimista · `AgendamientoService` · `POST /citas` | T1, T6, `test_agendar_rechazar_duplicado…` | 002, 006 |
| N2 Disponibilidad en las 3 sucursales | US-01, US-16 | CU-01 | Mostrar libres/ocupadas de todas sus sucursales | `LectorSql.disponibilidad` · `GET /consultas/disponibilidad` | `test_disponibilidad_por_especialidad…` | 004 |
| N3 Evidencia de cambios y cancelaciones | US-17, US-19 | CU-04 | Usuario, fecha, hora y motivo en la misma transacción | `RegistroDeAuditoria`, `UnitOfWork.confirmar` · `POST /citas/{id}/cancelar` | T5, `test_cancelar_deja_auditoria…` | 003 |
| N4 Historial de no-shows | US-14, US-20 | CU-05 | Solo es no-show una cita agendada cuya hora ya pasó; no bloquea al paciente | `MaquinaDeEstadosDeCita`, `HoraYaPaso`, `PoliticaDeNoShow` · `POST /citas/{id}/no-show` | T8, `test_no_show_suma_al_historial…` | 005, 006 |
| N5 Control del sobrecupo | US-10 | CU-01 | El sobrecupo no excede el límite del médico | `SobrecupoDisponible`, `LimiteDeSobrecupo` · `PUT /medicos/{id}/sobrecupo` | T2 | 002, 006 |
| N6 Menos trabajo al reagendar | US-09, US-11, US-23, US-24 | CU-03 | Afectadas con contacto y estatus, la más próxima primero; reagendar crea cita vinculada | `cancelar_jornada`, `Reagendador` · `POST /jornadas/cancelar`, `POST /citas/{id}/reagendar` | T7, `test_cancelar_jornada_listar_afectados…` | 002, 004 |
| N7 Autorización de aseguradora | US-12 | CU-01 | Si la aseguradora la exige, la cita queda pendiente y bloquea la franja | `RequiereAutorizacion`, `PoliticaDeAutorizacion`, `Autorizacion` | T4 | 005, 006 |
| N8 Llegada y retrasos | US-07, US-08, US-09 | CU-02 | Tolerancia de 15 min: 1–15 consultar al médico; >15 no atendida | `Tolerancia`, `Reloj`, State Machine · `POST /citas/{id}/llegada` | T3 (14/15/16 min) | 001, 006 |
| N9 Confirmación y liberación | US-06, US-18, US-21 | Ext. CU-01 | Confirmar por el canal de origen; liberar tras 24 h sin respuesta | `ConfirmacionService`, `NotificadorPorCanal` | `test_confirmacion_…`, `test_sin_respuesta_en_24_horas…` | 003 |
| N10 Pacientes sin duplicados | US-02, US-03, US-22 | Apoyo CU-01 | Expediente único; un teléfono por paciente; datos actualizables | `Paciente`, `PacienteService` · `/pacientes` | `test_registro_de_paciente…` | 001 |
| N11 Reportes | US-15, US-24 | Consulta | Agrupar por sucursal y médico; tasa de no-show; tiempo de reagendado | `LectorSql.reporte` · `GET /consultas/reporte` | `test_reporte_consolidado…` | 004 |
| N12 Cierre de consulta | US-13 | Cierre | La cita se cierra como atendida con receta/estudios/nueva cita | `cerrar_consulta`, `CierreDeConsulta` · `POST /citas/{id}/cierre` | `test_cierre_de_consulta…` | 001 |

## Pruebas T1–T8 del informe de la Unidad 3
| # | Escenario | Resultado esperado | Prueba |
|---|---|---|---|
| T1 | Agendar un horario ocupado por otra sucursal | `HorarioNoDisponible` | `test_T1_*` (unitaria e integración) |
| T2 | Sobrecupo dentro y por encima del límite | Se acepta dentro; `SobrecupoExcedido` al superarlo | `test_T2_*` |
| T3 | Llegada con 14, 15 y 16 minutos | 14 y 15 en tolerancia con alerta; 16 no atendida | `test_T3_*` |
| T4 | Aseguradora que exige autorización, sin número | Cita pendiente de autorización | `test_T4_*` |
| T5 | Cancelar y forzar fallo al guardar la auditoría | Nada se cancela (rollback) | `test_T5_*` |
| T6 | Dos confirmaciones simultáneas sobre la misma franja | La segunda falla por versión → `HorarioNoDisponible` | `test_T6_*` (sobre PostgreSQL en CI) |
| T7 | Cancelar jornada con tres citas | Tres afectadas y visibles en la consulta | `test_T7_*` |
| T8 | No-show a una cita ya atendida | `TransicionDeEstatusInvalida` | `test_T8_*` |
