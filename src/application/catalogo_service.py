"""CatalogoService: sucursales, especialidades, aseguradoras y médicos (sin reglas complejas)."""
from __future__ import annotations

from src.domain.catalogos import Aseguradora, Especialidad, Medico, Sucursal
from src.domain.errores import CatalogoNoEncontrado, DatosInvalidos, MedicoNoEncontrado
from src.domain.value_objects import LimiteDeSobrecupo


class CatalogoService:
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory

    def _crear(self, repo_attr, entidad):
        with self.uow_factory() as u:
            repo = getattr(u, repo_attr)
            if repo.obtener(entidad.id) is not None:
                raise DatosInvalidos(f"Ya existe '{entidad.id}'")
            repo.guardar(entidad)
            u.confirmar()
        return entidad

    def crear_sucursal(self, id, nombre):
        return self._crear("sucursales", Sucursal(id, nombre))

    def crear_especialidad(self, id, nombre):
        return self._crear("especialidades", Especialidad(id, nombre))

    def crear_aseguradora(self, id, nombre, exige_autorizacion=False, anticipacion_horas=0):
        if anticipacion_horas < 0:
            raise DatosInvalidos("La anticipación no puede ser negativa")
        return self._crear("aseguradoras", Aseguradora(id, nombre, exige_autorizacion, anticipacion_horas))

    def crear_medico(self, id, nombre, especialidades=(), limite_sobrecupo=0, por_honorarios=False):
        with self.uow_factory() as u:
            for e in especialidades:
                if u.especialidades.obtener(e) is None:
                    raise CatalogoNoEncontrado(f"Especialidad {e} no encontrada")
        return self._crear("medicos", Medico(id, nombre, tuple(especialidades),
                                             LimiteDeSobrecupo(limite_sobrecupo), por_honorarios))

    def definir_sobrecupo(self, medico_id, valor):  # US-10
        with self.uow_factory() as u:
            m = u.medicos.obtener(medico_id)
            if m is None:
                raise MedicoNoEncontrado(f"Médico {medico_id} no encontrado")
            m.definir_sobrecupo(valor)
            u.medicos.guardar(m)
            u.confirmar()
            return m

    def listar(self, tipo):
        with self.uow_factory() as u:
            return getattr(u, tipo).listar()
