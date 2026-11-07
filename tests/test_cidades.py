import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ibge  # noqa: E402
from app import create_app  # noqa: E402

# Estes testes NÃO acessam a internet: trocamos a busca real do IBGE por uma
# função falsa (monkeypatch), assim o teste é rápido e sempre dá o mesmo resultado.

CIDADES_FALSAS = ["Abaiara", "Acarape", "Acaraú", "Acopiara", "Aiuaba", "Altaneira"]


def test_cidades_sucesso_respeita_limite(monkeypatch):
    monkeypatch.setattr(ibge, "buscar_municipios", lambda uf: CIDADES_FALSAS)
    resp = create_app().test_client().get("/api/v1/cidades/CE?limite=5")
    assert resp.status_code == 200
    corpo = resp.get_json()
    assert corpo["uf"] == "CE"
    assert corpo["quantidade_retornada"] == 5
    assert corpo["cidades"][0] == {"nome": "Abaiara"}
    assert "consultado_em" in corpo


def test_cidades_limite_padrao_e_10(monkeypatch):
    monkeypatch.setattr(ibge, "buscar_municipios", lambda uf: [f"Cidade {i}" for i in range(30)])
    corpo = create_app().test_client().get("/api/v1/cidades/CE").get_json()
    assert corpo["quantidade_retornada"] == 10


def test_cidades_sigla_invalida_retorna_400():
    resp = create_app().test_client().get("/api/v1/cidades/ceara")
    assert resp.status_code == 400
    corpo = resp.get_json()
    assert corpo["erro"] is True
    assert corpo["codigo"] == "SIGLA_UF_INVALIDA"
    assert corpo["sigla_uf_informada"] == "ceara"


def test_cidades_limite_invalido_retorna_400():
    resp = create_app().test_client().get("/api/v1/cidades/CE?limite=500")
    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "LIMITE_INVALIDO"


def test_cidades_uf_inexistente_retorna_404(monkeypatch):
    def falso(uf):
        raise ibge.UFNaoEncontrada(uf)

    monkeypatch.setattr(ibge, "buscar_municipios", falso)
    resp = create_app().test_client().get("/api/v1/cidades/XX")
    assert resp.status_code == 404
    corpo = resp.get_json()
    assert corpo["codigo"] == "UF_NAO_ENCONTRADA"
    assert corpo["sigla_uf_informada"] == "XX"


def test_cidades_ibge_fora_do_ar_retorna_503(monkeypatch):
    def falso(uf):
        raise ibge.ServicoIndisponivel("IBGE")

    monkeypatch.setattr(ibge, "buscar_municipios", falso)
    resp = create_app().test_client().get("/api/v1/cidades/CE")
    assert resp.status_code == 503
    assert resp.get_json()["servico"] == "IBGE"
