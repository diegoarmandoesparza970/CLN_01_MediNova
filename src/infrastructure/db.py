"""Modelo relacional (solo infraestructura: el dominio no conoce estas clases)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class SucursalRow(Base):
    __tablename__ = "sucursales"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class EspecialidadRow(Base):
    __tablename__ = "especialidades"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class AseguradoraRow(Base):
    __tablename__ = "aseguradoras"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    exige_autorizacion: Mapped[bool] = mapped_column(Boolean, default=False)
    anticipacion_horas: Mapped[int] = mapped_column(Integer, default=0)


class MedicoRow(Base):
    __tablename__ = "medicos"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    especialidades: Mapped[list] = mapped_column(JSON, default=list)
    limite_sobrecupo: Mapped[int] = mapped_column(Integer, default=0)
    por_honorarios: Mapped[bool] = mapped_column(Boolean, default=False)


class PacienteRow(Base):
    __tablename__ = "pacientes"
    expediente: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    telefono: Mapped[str] = mapped_column(String(30))
    telefono_normalizado: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    correo: Mapped[str] = mapped_column(String(160), default="")
    nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    aseguradora_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SecuenciaRow(Base):
    __tablename__ = "secuencias"
    nombre: Mapped[str] = mapped_column(String(40), primary_key=True)
    valor: Mapped[int] = mapped_column(Integer, default=0)


class AgendaRow(Base):
    __tablename__ = "agendas"
    medico_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class JornadaRow(Base):
    __tablename__ = "jornadas"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    medico_id: Mapped[str] = mapped_column(String(40), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    sucursal_id: Mapped[str] = mapped_column(String(40))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime] = mapped_column(DateTime)
    cancelada: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_jornadas_agenda", "medico_id", "fecha"),)


class CitaRow(Base):
    __tablename__ = "citas"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    medico_id: Mapped[str] = mapped_column(String(40))
    fecha: Mapped[date] = mapped_column(Date)
    expediente: Mapped[str] = mapped_column(String(20), index=True)
    sucursal_id: Mapped[str] = mapped_column(String(40))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime] = mapped_column(DateTime)
    especialidad: Mapped[str] = mapped_column(String(40), default="")
    motivo: Mapped[str] = mapped_column(Text, default="")
    canal: Mapped[str] = mapped_column(String(20), default="recepcion")
    aseguradora_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    aut_estado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aut_numero: Mapped[str | None] = mapped_column(String(60), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), index=True)
    cita_origen_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    llegada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conf_envio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conf_canal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    conf_respuesta: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cierre_receta: Mapped[str | None] = mapped_column(Text, nullable=True)
    cierre_estudios: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cierre_nueva_cita: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    creada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reagendada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_citas_agenda", "medico_id", "fecha"),)


class AuditoriaRow(Base):
    """Solo se inserta: nunca se actualiza ni se borra (invariante, informe sección 3)."""
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cita_id: Mapped[str] = mapped_column(String(40), index=True)
    tipo: Mapped[str] = mapped_column(String(40))
    usuario: Mapped[str] = mapped_column(String(80))
    fecha: Mapped[datetime] = mapped_column(DateTime)
    motivo: Mapped[str] = mapped_column(Text)


class NotificacionRow(Base):
    __tablename__ = "notificaciones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cita_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expediente: Mapped[str] = mapped_column(String(20))
    canal: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(40))
    texto: Mapped[str] = mapped_column(Text)
    creada_en: Mapped[datetime] = mapped_column(DateTime)


def crear_engine(url: str):
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


def crear_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)


def crear_esquema(engine):
    Base.metadata.create_all(engine)


def borrar_esquema(engine):
    Base.metadata.drop_all(engine)
