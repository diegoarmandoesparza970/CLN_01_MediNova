# Glosario de dominio (lenguaje ubicuo)

Los nombres de clases, endpoints, tablas y pruebas usan estos términos. **35 términos**: 19 de la Unidad 2, 8 de los complementos de la Unidad 2 (con la definición de *Tolerancia por retraso* corregida) y 8 nuevos del PIA.

| # | Término | Definición | En el código |
|---|---|---|---|
| 1 | Cita médica | Reserva programada de un bloque de tiempo en una sucursal, fecha y hora específicas, que vincula a un paciente con un médico. | `Cita` |
| 2 | No-show | El paciente agendó y no se presentó ni canceló. Se marca cuando la hora ya pasó. | `EstadoCita.NO_SHOW` |
| 3 | Sobrecupo | Cita adicional en un horario ya ocupado, dentro del límite que el médico acepta. | `SobrecupoDisponible` |
| 4 | Número de expediente | Identificador único e irrepetible del paciente entre sucursales. | `Paciente.expediente` |
| 5 | Convenio con aseguradora | Acuerdo que permite atender bajo la cobertura de una aseguradora, previa validación o autorización. | `Aseguradora` |
| 6 | Jornada médica | Rango de horas que un médico ofrece en una sucursal. | `Jornada` |
| 7 | Confirmación de cita | Aviso preventivo un día antes para validar la asistencia. | `Confirmacion` |
| 8 | Registro de recepción | Acto presencial en que el paciente reporta su llegada. | `registrar_llegada` |
| 9 | Tolerancia por retraso | Margen de **15 minutos** de retraso dentro del cual recepción consulta al médico si puede atender; pasado ese margen la cita queda no atendida por retraso. *(Definición corregida respecto a U2, que estaba invertida.)* | `Tolerancia` |
| 10 | Médico por honorarios | Profesional sin relación laboral fija con disponibilidad que cambia cada semana. | `Medico.por_honorarios` |
| 11 | Autorización de aseguradora | Clave o dictamen que valida la cobertura de la atención. | `Autorizacion` |
| 12 | Reagendamiento | Cambio de fecha, hora, médico o sucursal de una cita previa; crea una cita vinculada y conserva el registro original. | `Reagendador` |
| 13 | Agenda compartida | Herramienta **manual actual** donde recepción ve la disponibilidad. Distinta de *Agenda médica*. | (sistema actual) |
| 14 | Cita duplicada | Dos citas del mismo médico en un espacio temporal idéntico o traslapado. | `HorarioNoDisponible` |
| 15 | Sucursal | Unidad física del grupo MediNova. | `Sucursal` |
| 16 | Orden de estudio / procedimiento | Solicitud derivada de una consulta para análisis o procedimientos menores. | `CierreDeConsulta.estudios` |
| 17 | Receta médica | Documento con las prescripciones al finalizar la consulta. | `CierreDeConsulta.receta` |
| 18 | Cancelación de jornada | Interrupción imprevista de la disponibilidad que un médico ofreció. | `cancelar_jornada` |
| 19 | Especialidad médica | Rama en la que un médico tiene competencias. | `Especialidad` |
| 20 | Canal de solicitud | Medio por el que el paciente pide la cita: teléfono, WhatsApp o recepción. | `CanalDeSolicitud` |
| 21 | Estatus de la cita | Estado del ciclo de vida: agendada, pendiente de autorización, presente, atendida, no-show, no atendida por retraso, cancelada, afectada, reagendada. | `EstadoCita` |
| 22 | Cierre de consulta | Registro de receta, estudios y/o nueva cita al terminar la atención. | `cerrar_consulta` |
| 23 | Historial de no-shows | Conteo y fechas de no-shows de un paciente, calculado desde las citas. | `HistorialNoShowsVM` |
| 24 | Registro de auditoría | Evidencia inmutable de usuario, fecha, hora y motivo de una cancelación o modificación. | `RegistroDeAuditoria` |
| 25 | Recepcionista | Único rol que agenda, modifica y cancela citas. | `Rol.RECEPCION` |
| 26 | Personal administrativo | Rol que da seguimiento a políticas y reportes. | `Rol.ADMINISTRATIVO` |
| 27 | Dirección | Rol patrocinador; define políticas y consulta reportes. | `Rol.DIRECCION` |
| 28 | Agenda médica del día | Conjunto de jornadas y citas de un médico en una fecha, en **todas** sus sucursales (Aggregate raíz). | `AgendaMedica` |
| 29 | Franja horaria | Intervalo de inicio y fin dentro de una jornada en el que se agenda una cita. | `FranjaHoraria` |
| 30 | Límite de sobrecupo | Citas adicionales que un médico acepta en un horario ocupado; cero si no acepta. | `LimiteDeSobrecupo` |
| 31 | Política de no-show | Regla sobre qué ocurre tras cierto número de no-shows; la aprueba dirección. | `PoliticaDeNoShow` |
| 32 | Cita afectada | Cita de una jornada cancelada que espera reagendarse o cancelarse. | `EstadoCita.AFECTADA` |
| 33 | Cita vinculada | Cita nueva creada al reagendar; apunta a la cita original. | `Cita.cita_origen_id` |
| 34 | Pendiente de autorización | Cita de una aseguradora que exige autorización y aún no tiene número; bloquea la franja. | `EstadoCita.PENDIENTE_AUTORIZACION` |
| 35 | Liberación por falta de confirmación | Cancelación automática del horario si el paciente no responde en 24 h. | `liberar_sin_confirmacion` |
