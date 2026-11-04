"""PacienteService: US-02, US-03, US-22 (zona de Transaction Script, ADR-001)."""
from __future__ import annotations

from src.domain.catalogos import Paciente
from src.domain.errores import PacienteDuplicado, PacienteNoEncontrado
from src.domain.value_objects import Contacto

from .comandos import ActualizarPacienteCommand, RegistrarPacienteCommand


class PacienteService:
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory

    def registrar_paciente(self, cmd: RegistrarPacienteCommand) -> str:
        contacto = Contacto(cmd.telefono, cmd.correo)
        with self.uow_factory() as u:
            existente = u.pacientes.buscar_por_telefono(contacto.telefono_normalizado)
            if existente:
                raise PacienteDuplicado(existente.expediente)
            expediente = u.pacientes.siguiente_numero_de_expediente()
            paciente = Paciente.registrar(expediente, cmd.nombre, contacto, cmd.nacimiento, cmd.aseguradora_id)
            u.pacientes.agregar(paciente)
            u.vistos.append(paciente)
            u.confirmar()
        return expediente

    def buscar(self, expediente: str | None = None, telefono: str | None = None) -> Paciente:
        with self.uow_factory() as u:
            if expediente:
                p = u.pacientes.obtener_por_expediente(expediente)
            elif telefono:
                p = u.pacientes.buscar_por_telefono(Contacto(telefono).telefono_normalizado)
            else:
                p = None
            if p is None:
                raise PacienteNoEncontrado("Paciente no encontrado")
            return p

    def actualizar_paciente(self, cmd: ActualizarPacienteCommand) -> Paciente:
        with self.uow_factory() as u:
            p = u.pacientes.obtener_por_expediente(cmd.expediente)
            if p is None:
                raise PacienteNoEncontrado(f"Paciente {cmd.expediente} no encontrado")
            p.actualizar_datos(cmd.telefono, cmd.correo, cmd.aseguradora_id, cmd.actualiza_aseguradora)
            u.pacientes.guardar(p)
            u.vistos.append(p)
            u.confirmar()
            return p
