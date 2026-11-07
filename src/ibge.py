"""Acesso à API de Localidades do IBGE.

Este arquivo só se preocupa em falar com o IBGE. As rotas (app.py) chamam
as funções daqui e decidem qual resposta devolver ao usuário.
"""
import unicodedata

import requests

BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"
TIMEOUT = 5  # segundos de espera antes de desistir do IBGE


class ServicoIndisponivel(Exception):
    """O IBGE não respondeu ou respondeu algo inesperado."""


class UFNaoEncontrada(Exception):
    """O IBGE não conhece a sigla de estado informada."""


def _sem_acento(texto):
    # Usado só para ordenar: "Acaraú" fica junto de "Acarape", sem acento atrapalhar.
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn").lower()


def buscar_municipios(uf):
    """Devolve a lista de nomes dos municípios de um estado, em ordem alfabética."""
    url = f"{BASE_URL}/estados/{uf}/municipios"

    try:
        resposta = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException:
        raise ServicoIndisponivel("IBGE")

    if resposta.status_code in (400, 404):
        raise UFNaoEncontrada(uf)
    if resposta.status_code != 200:
        raise ServicoIndisponivel("IBGE")

    try:
        dados = resposta.json()
    except ValueError:
        raise ServicoIndisponivel("IBGE")

    if not dados:  # lista vazia: estado que não existe
        raise UFNaoEncontrada(uf)

    nomes = [item["nome"] for item in dados]
    return sorted(nomes, key=_sem_acento)


# O Open-Meteo informa o estado por extenso ("Ceará"); a resposta da nossa API
# usa a sigla ("CE"). Para converter, perguntamos ao IBGE a lista dos 27 estados
# uma única vez e guardamos na memória (cache) para as próximas consultas.
_cache_estados = None
_APELIDOS = {"federal district": "distrito federal"}


def buscar_sigla_estado(nome_estado):
    """Converte "Ceará" em "CE". Devolve None se não conseguir (sem derrubar a API)."""
    global _cache_estados
    if not nome_estado:
        return None

    if _cache_estados is None:
        try:
            resposta = requests.get(f"{BASE_URL}/estados", timeout=TIMEOUT)
            resposta.raise_for_status()
            _cache_estados = {_sem_acento(e["nome"]): e["sigla"] for e in resposta.json()}
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    chave = _sem_acento(nome_estado)
    chave = _APELIDOS.get(chave, chave)
    return _cache_estados.get(chave)
