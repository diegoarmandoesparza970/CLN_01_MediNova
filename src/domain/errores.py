"""Errores de negocio expresados en el lenguaje ubicuo (informe, sección 4)."""


class ErrorDeDominio(Exception):
    """Base de todo error de negocio. La API lo traduce a HTTP."""

    codigo = "error_de_dominio"


class HorarioNoDisponible(ErrorDeDominio):
    codigo = "horario_no_disponible"


class SobrecupoExcedido(ErrorDeDominio):
    codigo = "sobrecupo_excedido"


class FranjaFueraDeJornada(ErrorDeDominio):
    codigo = "franja_fuera_de_jornada"


class JornadaTraslapada(ErrorDeDominio):
    codigo = "jornada_traslapada"


class TransicionDeEstatusInvalida(ErrorDeDominio):
    codigo = "transicion_de_estatus_invalida"


class ConflictoDeVersion(ErrorDeDominio):
    codigo = "conflicto_de_version"


class CitaSolapadaDelPaciente(ErrorDeDominio):
    codigo = "cita_solapada_del_paciente"


class PacienteDuplicado(ErrorDeDominio):
    codigo = "paciente_duplicado"

    def __init__(self, expediente: str):
        super().__init__(f"Ya existe un paciente con ese teléfono (expediente {expediente})")
        self.expediente = expediente


class DatosInvalidos(ErrorDeDominio):
    codigo = "datos_invalidos"


class NoEncontrado(ErrorDeDominio):
    codigo = "no_encontrado"


class CitaNoEncontrada(NoEncontrado):
    codigo = "cita_no_encontrada"


class PacienteNoEncontrado(NoEncontrado):
    codigo = "paciente_no_encontrado"


class MedicoNoEncontrado(NoEncontrado):
    codigo = "medico_no_encontrado"


class CatalogoNoEncontrado(NoEncontrado):
    codigo = "catalogo_no_encontrado"


class PermisoDenegado(ErrorDeDominio):
    codigo = "permiso_denegado"
