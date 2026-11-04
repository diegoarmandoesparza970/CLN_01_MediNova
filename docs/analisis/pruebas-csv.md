# Pruebas con el paquete de datos CSV del PIA

El paquete entregado por el docente (`tests/datos_csv/`) contiene 40 pacientes, 20 recursos (consultas y estudios), 60 operaciones con 117 líneas de detalle, 120 casos de prueba y 20 pruebas de transición. Todos los datos son ficticios.

## Diferencias con el modelo propio (documentadas, como pide el LEEME)
El LEEME aclara que su modelo es "propuesto" y que no reemplaza los requerimientos del equipo. Por eso el dominio de MediNova (agendas, citas, jornadas) **no cambia**: el paquete se ejecuta con un modelo auxiliar en `tests/csv_modelo/` que reutiliza la infraestructura real (`Especificacion` con `&`, `|`, `~`, `ErrorDeDominio`, tabla de transiciones) y se contrasta con la API real.

| Concepto del paquete | Equivalente en MediNova | Diferencia |
|---|---|---|
| Actor (paciente), `activo` | `Paciente` | El paciente de MediNova no tiene bandera de baja; se modela solo en el auxiliar |
| Recurso (precio, capacidad) | Especialidad / horario de la jornada | MediNova no cobra por línea; la capacidad real es la franja del médico |
| Operación con líneas y total | Cita | Una cita no tiene líneas; el total se calcula con `Decimal` solo en el auxiliar |
| Estados SOLICITADA→CONFIRMADA→ATENDIDA / CANCELADA | `agendada`→`presente`→`atendida` / `cancelada` | Misma idea de máquina de estados con tabla única de transiciones |
| `puede_procesarse` | Specifications de agendado (`PacienteSinCitaSolapada`, `HorarioLibre`…) | Mismo patrón; reglas distintas |

## Reglas ejecutadas
1. `puede_procesarse` = `ActorActivo & DetalleNoVacio & OperacionAutorizada`.
2. `beneficio_referencia` = `ActorPreferente & TotalMinimo(1500) & ~PromocionActiva` (umbral inclusivo, importes con `Decimal`).
3. `LineasValidas` (cantidad > 0, dentro de la capacidad, recurso habilitado) como verificación de calidad de datos.
4. Transiciones: `aprobar` (exige `puede_procesarse`), `atender`, `cancelar`; cada cambio emite un evento (`OperacionConfirmada`, `OperacionAtendida`, `OperacionCancelada`).

**Interpretación de las acciones sugeridas** (el paquete no trae resultados esperados): `aprobar` → CONFIRMADA; `completar` → aprobar y atender; `cancelar` → CANCELADA; `repetir_aprobacion` → aprobar dos veces (la segunda es inválida); `saltar_estado` → atender directamente desde SOLICITADA (inválido).

## Resultados
Se ejecutan con `python -m scripts.ejecutar_csv` (escribe `docs/evidencias/csv/resultados_casos_prueba.csv` y `resultados_transiciones.csv`) y automáticamente en `tests/integration/test_datos_csv.py`, que compara cada resultado con un **oráculo independiente** escrito en Python plano directamente sobre las filas del CSV.

| Conjunto | Casos | Resultado |
|---|---|---|
| `validar_operacion` | 60 | 47 CUMPLE · 13 NO_CUMPLE |
| `evaluar_beneficio` | 60 | 9 CUMPLE · 51 NO_CUMPLE |
| Transiciones | 20 | 20 coinciden con el oráculo |

Hallazgos de calidad de datos: 5 pacientes inactivos (C007, C014, C021, C028, C035); 2 operaciones sin detalle (O013, O039); 6 operaciones con una línea de recurso deshabilitado (O005, O015, O020, O035, O040, O055); 7 operaciones sin autorización (O008, O016, O024, O032, O040, O048, O056); ninguna cantidad excede la capacidad del recurso. Las transiciones S008, S013 y S016 son rechazadas con `precondicion_no_cumplida` porque su operación no cumple `puede_procesarse`; es el comportamiento esperado de la regla.

## Contraste con la API
Los 40 pacientes del CSV se registran por `POST /pacientes` (201), se consultan por expediente (200), un teléfono repetido responde 409, un expediente inexistente 404 y datos inválidos 422.
