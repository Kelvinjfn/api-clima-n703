import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import openmeteo  # noqa: E402
from app import create_app  # noqa: E402
from saude import JANELA_SEGUNDOS, MonitorServicos  # noqa: E402

CIDADE_FALSA = {"nome": "Fortaleza", "estado_nome": "Ceará", "latitude": -3.7, "longitude": -38.5}
CLIMA_FALSO = {"minima": 24.0, "maxima": 31.0, "codigo": 2}


def _falhar(nome):
    raise openmeteo.ServicoIndisponivel("Open-Meteo")


def test_health_retorna_200_e_healthy():
    client = create_app().test_client()
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    corpo = resp.get_json()
    assert corpo["status"] == "healthy"
    assert corpo["versao"] == "1.0.0"
    assert "timestamp" in corpo
    assert "motivo" not in corpo


def test_health_fica_degraded_apos_falha_de_servico_externo(monkeypatch):
    client = create_app().test_client()
    monkeypatch.setattr(openmeteo, "buscar_cidade", _falhar)

    assert client.get("/api/v1/clima/Fortaleza").status_code == 503

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200  # continua 200: a API está no ar
    corpo = resp.get_json()
    assert corpo["status"] == "degraded"
    assert corpo["motivo"] == "Serviço externo indisponível"
    assert corpo["versao"] == "1.0.0"


def test_health_volta_a_healthy_apos_um_sucesso(monkeypatch):
    client = create_app().test_client()

    monkeypatch.setattr(openmeteo, "buscar_cidade", _falhar)
    client.get("/api/v1/clima/Fortaleza")
    assert client.get("/api/v1/health").get_json()["status"] == "degraded"

    monkeypatch.setattr(openmeteo, "buscar_cidade", lambda nome: CIDADE_FALSA)
    monkeypatch.setattr(openmeteo, "buscar_clima", lambda lat, lon: CLIMA_FALSO)
    assert client.get("/api/v1/clima/Fortaleza").status_code == 200

    assert client.get("/api/v1/health").get_json()["status"] == "healthy"


def test_degraded_expira_depois_da_janela_de_tempo(monkeypatch):
    agora = [1000.0]  # relógio falso, que controlamos à mão
    monitor = MonitorServicos(relogio=lambda: agora[0])
    client = create_app(monitor=monitor).test_client()

    monkeypatch.setattr(openmeteo, "buscar_cidade", _falhar)
    client.get("/api/v1/clima/Fortaleza")
    assert client.get("/api/v1/health").get_json()["status"] == "degraded"

    agora[0] += JANELA_SEGUNDOS + 1  # passa mais de 1 minuto sem novas falhas
    assert client.get("/api/v1/health").get_json()["status"] == "healthy"
