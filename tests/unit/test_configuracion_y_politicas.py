import pytest

from src.domain.catalogos import Paciente
from src.domain.politicas import AlertaPorUmbralDeNoShows, SinSancionPorNoShow
from src.domain.value_objects import Contacto
from src.infrastructure.config import Configuracion, normalizar_url_db
from src.infrastructure.reloj import RelojDelSistema, RelojFijo
from tests.conftest import AHORA

pytestmark = pytest.mark.traza("ADR-005", "ADR-007")


def test_politicas_de_no_show_son_intercambiables():
    assert SinSancionPorNoShow().evaluar(10) is None
    p = AlertaPorUmbralDeNoShows(2)
    assert p.evaluar(1) is None and "2 no-shows" in p.evaluar(2)


def test_configuracion_desde_entorno_12_factor(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/d")
    monkeypatch.setenv("TOLERANCIA_MINUTOS", "10")
    monkeypatch.setenv("SEED_DEMO", "true")
    monkeypatch.setenv("NOSHOW_UMBRAL", "5")
    c = Configuracion.desde_entorno()
    assert c.database_url == "postgresql+psycopg2://u:p@h:5432/d"
    assert (c.tolerancia_minutos, c.seed_demo, c.noshow_umbral) == (10, True, 5)
    monkeypatch.delenv("SEED_DEMO")
    assert Configuracion.desde_entorno().seed_demo is False


def test_normalizar_url_db():
    assert normalizar_url_db("postgresql://a/b") == "postgresql+psycopg2://a/b"
    assert normalizar_url_db("sqlite://") == "sqlite://"


def test_relojes():
    r = RelojFijo(AHORA)
    assert r.ahora() == AHORA
    assert RelojDelSistema("America/Monterrey").ahora().tzinfo is None


def test_paciente_actualiza_datos():
    p = Paciente.registrar("E1", " Ana ", Contacto("8112345678"))
    assert p.nombre == "Ana"
    p.actualizar_datos(telefono="8187654321", correo="a@b.c", aseguradora_id="X", cambia_aseguradora=True)
    assert p.contacto.telefono == "8187654321" and p.aseguradora_id == "X"
    assert len(p.recoger_eventos()) == 2 and p.recoger_eventos() == []
