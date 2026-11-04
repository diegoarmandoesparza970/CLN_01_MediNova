# Historias de usuario con criterios de aceptación (Gherkin)

24 historias (mínimo exigido: 15). US-01 a US-18 provienen de la Unidad 2; US-19 a US-24 son los complementos acordados en el informe de la Unidad 3 y quedan **aprobadas por el equipo** en este PIA. Cada historia indica la necesidad del BRD que atiende, el caso de uso, el endpoint, el componente de dominio/aplicación y se verifica con pruebas marcadas `@pytest.mark.traza("US-xx")`.

| ID | Necesidad | Caso de uso | Endpoint | Componente |
|---|---|---|---|---|
| US-01 | N2 | CU-01 | `GET /consultas/disponibilidad` | DisponibilidadReader (LectorSql.disponibilidad) |
| US-02 | N10 | Apoyo CU-01 | `POST /pacientes` | PacienteService.registrar_paciente, Paciente |
| US-03 | N10 | Apoyo CU-01 | `GET /pacientes, POST /pacientes (409)` | PacienteRepository.buscar_por_telefono, PacienteDuplicado |
| US-04 | N1 | CU-01 | `POST /citas` | AgendamientoService.agendar_cita, AgendaMedica.agendar |
| US-05 | N1 | CU-01 | `POST /citas (409 horario_no_disponible)` | HorarioLibre, AgendaMedica (versión optimista) |
| US-06 | N9 | Extensión CU-01 | `POST /citas/confirmaciones/enviar, POST /citas/{id}/confirmacion` | ConfirmacionService, Confirmacion (VO) |
| US-07 | N8 | CU-02 | `POST /citas/{id}/llegada` | AtencionService.registrar_llegada, AgendaMedica.registrar_llegada |
| US-08 | N8 | CU-02 | `POST /citas/{id}/llegada (resultado consultar_medico)` | Tolerancia.evaluar |
| US-09 | N6, N8 | CU-02 | `POST /citas/{id}/llegada, /no-atendida-por-retraso, /reagendar` | Reagendador, EstadoCita.NO_ATENDIDA_POR_RETRASO |
| US-10 | N5 | CU-01 | `PUT /medicos/{id}/sobrecupo, POST /citas (409 sobrecupo_excedido)` | LimiteDeSobrecupo, SobrecupoDisponible |
| US-11 | N6 | CU-03 | `POST /jornadas/cancelar, GET /consultas/citas-afectadas` | JornadaService.cancelar_jornada, CitasAfectadas (lector) |
| US-12 | N7 | CU-01 | `POST /citas, POST /citas/{id}/autorizacion, /pago-particular` | PoliticaDeAutorizacion, RequiereAutorizacion, Autorizacion |
| US-13 | N12 | Cierre | `POST /citas/{id}/cierre` | AtencionService.cerrar_consulta, CierreDeConsulta |
| US-14 | N4 | CU-05 | `GET /consultas/historial-no-shows/{expediente}` | HistorialNoShowsReader, PoliticaDeNoShow |
| US-15 | N11 | Reporte | `GET /consultas/reporte` | ReporteReader (LectorSql.reporte) |
| US-16 | N2 | CU-01 | `GET /consultas/disponibilidad` | DisponibilidadDelMedicoVM |
| US-17 | N3 | CU-04 | `GET /consultas/auditoria` | RegistroDeAuditoria, UnitOfWork.confirmar (ADR-003) |
| US-18 | N9 | Extensión CU-01 | `POST /citas (canal), GET /consultas/notificaciones` | NotificadorPorCanal, CanalDeSolicitud |
| US-19 | N3 | CU-04 | `POST /citas/{id}/cancelar, POST /citas/{id}/modificar` | AgendaMedica.cancelar / modificar, MotivoDeCambio |
| US-20 | N4 | CU-05 | `POST /citas/{id}/no-show` | MaquinaDeEstadosDeCita, HoraYaPaso |
| US-21 | N9 | Extensión CU-01 | `POST /citas/confirmaciones/liberar-sin-respuesta` | ConfirmacionService.liberar_sin_confirmacion |
| US-22 | N10 | CU-02 | `PATCH /pacientes/{id}, POST /citas/{id}/llegada` | Paciente.actualizar_datos |
| US-23 | N6 | CU-03 | `GET /consultas/citas-afectadas` | AgendaMedica.cancelar_jornada (orden) |
| US-24 | N6, N11 | CU-03 | `GET /consultas/reporte (tiempo_promedio_reagendado_min)` | ReporteConsolidadoVM |

## US-01

**Como** recepcionista, **quiero** buscar la disponibilidad de un médico por especialidad y sucursal, **para** ofrecer horarios válidos sin llamar a otras sucursales.

```gherkin
Given un médico tiene jornadas registradas para una especialidad y sucursal
When la recepcionista busca disponibilidad por médico, especialidad y sucursal
Then el sistema muestra únicamente los horarios libres de ese médico en esa sucursal
```

## US-02

**Como** recepcionista, **quiero** registrar los datos de un paciente nuevo (nombre, teléfono, fecha de nacimiento, correo), **para** identificarlo en futuras visitas.

```gherkin
Given un paciente no tiene expediente previo
When la recepcionista captura nombre, teléfono, fecha de nacimiento y correo
Then el sistema crea un nuevo expediente con un número único de paciente
```

## US-03

**Como** recepcionista, **quiero** buscar a un paciente existente por teléfono o número de expediente, **para** agendar su cita sin duplicar su registro.

```gherkin
Given un paciente ya cuenta con expediente
When la recepcionista busca por teléfono o número de expediente
Then el sistema muestra el expediente correspondiente
And rechaza crear un duplicado con el mismo teléfono
```

## US-04

**Como** recepcionista, **quiero** agendar una cita registrando paciente, médico, especialidad, sucursal, fecha, hora, motivo y aseguradora (si aplica), **para** dejar el registro completo desde el primer contacto.

```gherkin
Given un horario disponible de un médico dentro de una jornada vigente
When la recepcionista completa todos los campos requeridos de la cita
Then el sistema guarda la cita con estatus "agendada" y bloquea ese horario
```

## US-05

**Como** recepcionista, **quiero** que el sistema bloquee automáticamente un horario ya ocupado por otra sucursal, **para** evitar citas duplicadas del mismo médico.

```gherkin
Given un horario de un médico ya está ocupado por una cita agendada en cualquier sucursal
When una recepcionista intenta agendar ese horario
Then el sistema rechaza la solicitud y muestra un mensaje de horario no disponible
And si dos recepcionistas confirman a la vez, la segunda también es rechazada
```

## US-06

**Como** recepcionista, **quiero** enviar una confirmación al paciente un día antes de su cita, **para** reducir el riesgo de no-shows.

```gherkin
Given una cita agendada para el día siguiente
When se ejecuta el proceso de confirmación
Then el sistema envía un recordatorio y registra si fue confirmado, rechazado o sin respuesta
```

## US-07

**Como** recepcionista, **quiero** registrar la llegada del paciente, **para** llevar control de asistencia.

```gherkin
Given una cita con estatus "agendada" para el día en curso
When el paciente se presenta en recepción
Then el sistema cambia el estatus a "presente" con la hora real de llegada
```

## US-08

**Como** recepcionista, **quiero** que el sistema marque cuando un paciente llega hasta 15 minutos tarde, **para** consultar al médico si puede atenderlo.

```gherkin
Given una cita con hora programada
When el paciente llega entre 1 y 15 minutos después de la hora programada
Then el sistema alerta a la recepcionista para confirmar con el médico si procede la atención
```

## US-09

**Como** recepcionista, **quiero** marcar una cita como "no atendida por retraso" cuando el retraso supera el límite, **para** ofrecer reagendado sin perder el registro original.

```gherkin
Given una cita con retraso mayor al límite definido (16 minutos o más)
When recepción decide no atender al paciente en ese horario
Then el sistema marca la cita como "no atendida por retraso"
And permite generar una nueva cita vinculada
```

## US-10

**Como** recepcionista (a indicación del médico), **quiero** registrar si un médico acepta sobrecupo y cuántos pacientes, **para** controlar la carga adicional del médico.

```gherkin
Given un médico que permite sobrecupo con un límite configurado
When recepción intenta agendar una cita adicional en un horario ya ocupado
Then el sistema permite la cita solo si no se supera el límite de sobrecupo de ese médico
```

## US-11

**Como** recepcionista, **quiero** ver la lista de pacientes afectados cuando un médico cancela su jornada, **para** localizarlos y reagendarlos.

```gherkin
Given un médico cancela su jornada
When recepción consulta las citas afectadas
Then el sistema muestra la lista de pacientes, sus datos de contacto y el estatus de reagendado o pendiente
```

## US-12

**Como** recepcionista, **quiero** registrar si una aseguradora requiere autorización previa, **para** evitar rechazos el día de la cita.

```gherkin
Given una cita asociada a una aseguradora que requiere autorización
When se agenda la cita
Then el sistema solicita el número de autorización o marca la cita como "pendiente de autorización"
```

## US-13

**Como** recepcionista (a partir de lo indicado por el médico), **quiero** registrar receta, estudios solicitados o una nueva cita al finalizar la consulta, **para** dar continuidad al tratamiento.

```gherkin
Given una consulta en curso (cita "presente")
When finaliza la atención
Then el sistema permite registrar receta, estudios y/o nueva cita
And cierra la cita como "atendida"
```

## US-14

**Como** personal administrativo, **quiero** consultar el historial de no-shows de un paciente, **para** aplicar la política correspondiente (una vez definida).

```gherkin
Given un paciente con una o más citas marcadas como no-show
When personal administrativo consulta su expediente
Then el sistema muestra el conteo y las fechas de no-shows registrados
```

## US-15

**Como** director de operaciones, **quiero** ver un reporte consolidado de citas, no-shows y ocupación por sucursal y por médico, **para** tomar decisiones de negocio.

```gherkin
Given un rango de fechas seleccionado
When el director genera el reporte
Then el sistema muestra citas agendadas, atendidas, no-shows y canceladas, agrupadas por sucursal y médico
```

## US-16

**Como** recepcionista, **quiero** ver la disponibilidad de un médico en las tres sucursales desde una sola pantalla, **para** mejorar la visibilidad entre sucursales.

```gherkin
Given un médico que atiende en más de una sucursal
When la recepcionista consulta su agenda
Then el sistema muestra los horarios disponibles y ocupados en todas las sucursales donde atiende
```

## US-17

**Como** personal administrativo, **quiero** que quede registrado quién modificó o canceló una cita y cuándo, **para** tener evidencia clara ante disputas.

```gherkin
Given una cita que es modificada o cancelada
When se guarda el cambio
Then el sistema registra usuario, fecha, hora y motivo del cambio en un historial de auditoría
And si el registro falla, el cambio no se guarda
```

## US-18

**Como** paciente, **quiero** solicitar mi cita por WhatsApp, teléfono o en recepción y recibir confirmación por el mismo canal, **para** usar el medio que me sea más cómodo.

```gherkin
Given un paciente solicita una cita por cualquiera de los canales disponibles
When la solicitud es procesada por recepción
Then el sistema registra el canal de origen y envía la confirmación por ese mismo canal
```

## US-19

**Como** recepcionista, **quiero** cancelar o modificar una cita indicando el motivo, **para** corregir la agenda dejando evidencia (corrección de alcance de U2).

```gherkin
Given una cita agendada o pendiente de autorización
When la recepcionista la cancela o la modifica indicando el motivo
Then la cita queda cancelada o modificada y el horario anterior se libera
And sin motivo el sistema rechaza el cambio
```

## US-20

**Como** recepcionista, **quiero** marcar como no-show una cita agendada cuya hora ya pasó sin llegada del paciente, **para** construir el historial de no-shows (corrección de alcance de U2).

```gherkin
Given una cita agendada cuya hora de inicio ya pasó
When la recepcionista la marca como no-show
Then el estatus cambia a "no_show" y suma al historial del paciente
And una cita ya atendida o con hora futura se rechaza
```

## US-21

**Como** recepcionista, **quiero** que el sistema libere el horario si el paciente no confirma en 24 horas, **para** reducir huecos por no-shows (deseo del stakeholder, decisión D7).

```gherkin
Given una cita con recordatorio enviado y sin respuesta
When pasan 24 horas o más
Then el sistema cancela la cita con el usuario "sistema", libera el horario y deja registro de auditoría
```

## US-22

**Como** recepcionista, **quiero** confirmar el teléfono y la aseguradora del paciente en cada visita, **para** mantener los datos vigentes (muchos cambian de convenio sin avisar).

```gherkin
Given un paciente que llega a su cita
When la recepcionista confirma o corrige su teléfono y su aseguradora
Then el sistema actualiza el expediente en la misma operación de llegada
```

## US-23

**Como** recepcionista, **quiero** ver los pacientes afectados ordenados por la cita más próxima primero, **para** llamarlos en el orden en que la práctica lo exige (P12, decisión D6).

```gherkin
Given una jornada cancelada con varias citas
When recepción consulta la lista de afectados
Then las citas aparecen ordenadas de la hora más próxima a la más lejana con su estatus de reagendado
```

## US-24

**Como** director de operaciones, **quiero** medir cuánto tarda recepción en reagendar cuando un médico cancela su jornada, **para** verificar el criterio de éxito de menor tiempo de reagendado.

```gherkin
Given citas reagendadas tras la cancelación de una jornada
When el director genera el reporte
Then el sistema muestra el tiempo promedio entre la cancelación de la jornada y el reagendado de las citas
```
