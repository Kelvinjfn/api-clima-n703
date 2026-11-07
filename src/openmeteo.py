"""Acesso à API do Open-Meteo (gratuita, sem chave).

Dois passos, nesta ordem:
  1) buscar_cidade: transforma o NOME da cidade em latitude/longitude (geocodificação)
  2) buscar_clima:  com latitude/longitude, pede a previsão do dia

As coordenadas NUNCA ficam fixas no código: sempre vêm do passo 1.
"""
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 5  # segundos de espera antes de desistir

# Códigos de tempo padrão WMO usados pelo Open-Meteo -> texto em português
CONDICOES = {
    0: "Céu Limpo",
    1: "Predominantemente Limpo",
    2: "Parcialmente Nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com Geada",
    51: "Garoa Leve",
    53: "Garoa Moderada",
    55: "Garoa Intensa",
    56: "Garoa Congelante Leve",
    57: "Garoa Congelante Intensa",
    61: "Chuva Fraca",
    63: "Chuva Moderada",
    65: "Chuva Forte",
    66: "Chuva Congelante Leve",
    67: "Chuva Congelante Forte",
    71: "Neve Fraca",
    73: "Neve Moderada",
    75: "Neve Forte",
    77: "Grãos de Neve",
    80: "Pancadas de Chuva Fracas",
    81: "Pancadas de Chuva Moderadas",
    82: "Pancadas de Chuva Fortes",
    85: "Pancadas de Neve Fracas",
    86: "Pancadas de Neve Fortes",
    95: "Trovoada",
    96: "Trovoada com Granizo Fraco",
    99: "Trovoada com Granizo Forte",
}


class ServicoIndisponivel(Exception):
    """O Open-Meteo não respondeu ou respondeu algo inesperado."""

    def __init__(self, servico="Open-Meteo"):
        super().__init__(servico)
        self.servico = servico


class CidadeNaoEncontrada(Exception):
    """Nenhuma cidade brasileira com esse nome."""


def descrever_condicao(codigo):
    return CONDICOES.get(codigo, "Condição Desconhecida")


def _pegar_json(url, parametros):
    try:
        resposta = requests.get(url, params=parametros, timeout=TIMEOUT)
    except requests.RequestException:
        raise ServicoIndisponivel()
    if resposta.status_code != 200:
        raise ServicoIndisponivel()
    try:
        return resposta.json()
    except ValueError:
        raise ServicoIndisponivel()


def buscar_cidade(nome):
    """Procura uma cidade BRASILEIRA pelo nome e devolve nome, estado e coordenadas."""
    dados = _pegar_json(
        GEOCODING_URL,
        {"name": nome, "count": 10, "language": "pt", "country_code": "BR", "format": "json"},
    )
    if not isinstance(dados, dict):
        raise ServicoIndisponivel()

    # Garantia extra: só aceitamos resultados do Brasil
    resultados = [r for r in dados.get("results", []) if r.get("country_code") == "BR"]
    if not resultados:
        raise CidadeNaoEncontrada(nome)

    primeiro = resultados[0]  # o Open-Meteo já ordena do mais relevante para o menos
    try:
        return {
            "nome": primeiro["name"],
            "estado_nome": primeiro.get("admin1"),
            "latitude": primeiro["latitude"],
            "longitude": primeiro["longitude"],
        }
    except KeyError:
        raise ServicoIndisponivel()


def buscar_clima(latitude, longitude):
    """Devolve temperatura mínima, máxima e código do tempo de hoje nessa coordenada."""
    dados = _pegar_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 1,
        },
    )
    try:
        diario = dados["daily"]
        minima = diario["temperature_2m_min"][0]
        maxima = diario["temperature_2m_max"][0]
        codigo = diario["weather_code"][0]
    except (KeyError, IndexError, TypeError):
        raise ServicoIndisponivel()

    if minima is None or maxima is None or codigo is None:
        raise ServicoIndisponivel()

    return {"minima": minima, "maxima": maxima, "codigo": codigo}
