import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ibge  # noqa: E402
import openmeteo  # noqa: E402
from app import create_app  # noqa: E402

# Como nos outros testes, trocamos as consultas reais por versões falsas (monkeypatch):
# o teste não depende da internet e sempre dá o mesmo resultado.

CIDADE_FALSA = {
    "nome": "Fortaleza",
    "estado_nome": "Ceará",
    "latitude": -3.71722,
    "longitude": -38.54306,
}
CLIMA_FALSO = {"minima": 24.2, "maxima": 31.8, "codigo": 2}


def test_clima_cidade_valida_retorna_200(monkeypatch):
    monkeypatch.setattr(openmeteo, "buscar_cidade", lambda nome: CIDADE_FALSA)
    monkeypatch.setattr(openmeteo, "buscar_clima", lambda lat, lon: CLIMA_FALSO)
    monkeypatch.setattr(ibge, "buscar_sigla_estado", lambda nome: "CE")

    resp = create_app().test_client().get("/api/v1/clima/Fortaleza")

    assert resp.status_code == 200
    corpo = resp.get_json()
    assert corpo["nome"] == "Fortaleza"
    assert corpo["estado"] == "CE"
    assert corpo["clima"]["temperatura_min"] == 24.2
    assert corpo["clima"]["temperatura_max"] == 31.8
    assert corpo["clima"]["condicao"] == "Parcialmente Nublado"
    assert corpo["clima"]["unidades"]["temperatura"] == "°C"
    assert "consultado_em" in corpo


def test_clima_cidade_nao_encontrada_retorna_404(monkeypatch):
    def falso(nome):
        raise openmeteo.CidadeNaoEncontrada(nome)

    monkeypatch.setattr(openmeteo, "buscar_cidade", falso)

    resp = create_app().test_client().get("/api/v1/clima/CidadeInexistente")

    assert resp.status_code == 404
    corpo = resp.get_json()
    assert corpo["erro"] is True
    assert corpo["codigo"] == "CIDADE_NAO_ENCONTRADA"
    assert corpo["nome_informado"] == "CidadeInexistente"


def test_clima_nome_invalido_retorna_400():
    resp = create_app().test_client().get("/api/v1/clima/X")

    assert resp.status_code == 400
    corpo = resp.get_json()
    assert corpo["codigo"] == "NOME_INVALIDO"
    assert corpo["nome_informado"] == "X"


def test_clima_servico_externo_fora_do_ar_retorna_503(monkeypatch):
    def falso(nome):
        raise openmeteo.ServicoIndisponivel("Open-Meteo")

    monkeypatch.setattr(openmeteo, "buscar_cidade", falso)

    resp = create_app().test_client().get("/api/v1/clima/Fortaleza")

    assert resp.status_code == 503
    corpo = resp.get_json()
    assert corpo["codigo"] == "SERVICO_EXTERNO_INDISPONIVEL"
    assert corpo["servico"] == "Open-Meteo"


def test_clima_sem_sigla_usa_nome_do_estado(monkeypatch):
    # Se o IBGE falhar na conversão, a API ainda responde (com o estado por extenso)
    monkeypatch.setattr(openmeteo, "buscar_cidade", lambda nome: CIDADE_FALSA)
    monkeypatch.setattr(openmeteo, "buscar_clima", lambda lat, lon: CLIMA_FALSO)
    monkeypatch.setattr(ibge, "buscar_sigla_estado", lambda nome: None)

    corpo = create_app().test_client().get("/api/v1/clima/Fortaleza").get_json()

    assert corpo["estado"] == "Ceará"


def test_descrever_condicao_conhecida_e_desconhecida():
    assert openmeteo.descrever_condicao(0) == "Céu Limpo"
    assert openmeteo.descrever_condicao(95) == "Trovoada"
    assert openmeteo.descrever_condicao(12345) == "Condição Desconhecida"


def test_rota_inexistente_responde_json():
    resp = create_app().test_client().get("/api/v1/qualquer-coisa")

    assert resp.status_code == 404
    assert resp.get_json()["codigo"] == "ROTA_NAO_ENCONTRADA"
