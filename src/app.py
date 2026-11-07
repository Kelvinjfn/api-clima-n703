from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

import ibge
import openmeteo
from saude import MonitorServicos

VERSAO = "1.0.0"
LIMITE_PADRAO = 10
LIMITE_MIN = 1
LIMITE_MAX = 100


def agora_iso():
    """Timestamp em UTC no formato ISO 8601 (ex.: 2026-11-01T14:30:00Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def erro(status, codigo, mensagem, **extras):
    """Monta a resposta de erro padronizada exigida pela proposta."""
    corpo = {"erro": True, "codigo": codigo, "mensagem": mensagem}
    corpo.update(extras)
    return jsonify(corpo), status


def create_app(monitor=None):
    monitor = monitor or MonitorServicos()  # lembra se os serviços externos falharam
    app = Flask(__name__)
    app.json.ensure_ascii = False  # mantém acentos (UTF-8) no JSON
    app.json.sort_keys = False     # mantém a ordem dos campos como escrevemos
    CORS(app)  # CORS habilitado para testes via navegador

    @app.get("/api/v1/health")
    def health():
        corpo = {"status": "healthy", "versao": VERSAO, "timestamp": agora_iso()}
        # Se uma consulta recente a um serviço externo falhou, avisamos que está degradado.
        # Continua HTTP 200: a API em si está no ar.
        if monitor.degradado():
            corpo["status"] = "degraded"
            corpo["motivo"] = "Serviço externo indisponível"
        return jsonify(corpo), 200

    @app.get("/api/v1/cidades/<sigla_uf>")
    def cidades_por_estado(sigla_uf):
        # 1) Validar a sigla: exatamente 2 letras (400 se não for)
        if len(sigla_uf) != 2 or not sigla_uf.isalpha():
            return erro(
                400,
                "SIGLA_UF_INVALIDA",
                "A sigla do estado deve conter exatamente 2 letras",
                sigla_uf_informada=sigla_uf,
            )
        uf = sigla_uf.upper()

        # 2) Validar o parâmetro opcional ?limite= (inteiro de 1 a 100, padrão 10)
        limite_texto = request.args.get("limite", str(LIMITE_PADRAO))
        try:
            limite = int(limite_texto)
        except ValueError:
            limite = None
        if limite is None or not (LIMITE_MIN <= limite <= LIMITE_MAX):
            return erro(
                400,
                "LIMITE_INVALIDO",
                f"O limite deve ser um número inteiro entre {LIMITE_MIN} e {LIMITE_MAX}",
                limite_informado=limite_texto,
            )

        # 3) Buscar no IBGE
        try:
            nomes = ibge.buscar_municipios(uf)
        except ibge.UFNaoEncontrada:
            monitor.registrar_sucesso()  # o IBGE respondeu normalmente
            return erro(
                404,
                "UF_NAO_ENCONTRADA",
                "Estado com a sigla informada não foi encontrado",
                sigla_uf_informada=sigla_uf,
            )
        except ibge.ServicoIndisponivel:
            monitor.registrar_falha()
            return erro(
                503,
                "SERVICO_EXTERNO_INDISPONIVEL",
                "Não foi possível obter dados do serviço externo. Tente novamente em alguns instantes",
                servico="IBGE",
            )

        monitor.registrar_sucesso()

        # 4) Montar a resposta de sucesso
        escolhidas = nomes[:limite]
        return jsonify(
            {
                "uf": uf,
                "quantidade_retornada": len(escolhidas),
                "cidades": [{"nome": nome} for nome in escolhidas],
                "consultado_em": agora_iso(),
            }
        ), 200

    @app.get("/api/v1/clima/<nome_cidade>")
    def clima_da_cidade(nome_cidade):
        # 1) Validar o nome: pelo menos 2 caracteres (400 se não for)
        nome = nome_cidade.strip()
        if len(nome) < 2:
            return erro(
                400,
                "NOME_INVALIDO",
                "O nome da cidade deve conter pelo menos 2 caracteres",
                nome_informado=nome_cidade,
            )

        # 2) Nome -> coordenadas (Open-Meteo) e coordenadas -> clima (Open-Meteo)
        try:
            cidade = openmeteo.buscar_cidade(nome)
            previsao = openmeteo.buscar_clima(cidade["latitude"], cidade["longitude"])
        except openmeteo.CidadeNaoEncontrada:
            monitor.registrar_sucesso()  # o Open-Meteo respondeu normalmente
            return erro(
                404,
                "CIDADE_NAO_ENCONTRADA",
                "Nenhuma cidade encontrada com o nome informado",
                nome_informado=nome_cidade,
            )
        except openmeteo.ServicoIndisponivel as e:
            monitor.registrar_falha()
            return erro(
                503,
                "SERVICO_EXTERNO_INDISPONIVEL",
                "Não foi possível obter dados do serviço externo. Tente novamente em alguns instantes",
                servico=e.servico,
            )

        monitor.registrar_sucesso()

        # 3) "Ceará" -> "CE" via IBGE. Se o IBGE falhar, usamos o nome por extenso
        #    em vez de derrubar a resposta inteira.
        estado = ibge.buscar_sigla_estado(cidade["estado_nome"]) or cidade["estado_nome"]

        # 4) Montar a resposta de sucesso
        return jsonify(
            {
                "nome": cidade["nome"],
                "estado": estado,
                "coordenadas": {
                    "latitude": cidade["latitude"],
                    "longitude": cidade["longitude"],
                },
                "clima": {
                    "temperatura_min": round(previsao["minima"], 1),
                    "temperatura_max": round(previsao["maxima"], 1),
                    "condicao": openmeteo.descrever_condicao(previsao["codigo"]),
                    "unidades": {"temperatura": "°C"},
                },
                "consultado_em": agora_iso(),
            }
        ), 200

    @app.errorhandler(404)
    def rota_nao_encontrada(_):
        # Garante JSON até para endereços que não existem (a proposta exige tudo em JSON)
        return erro(404, "ROTA_NAO_ENCONTRADA", "A rota informada não existe")

    @app.errorhandler(405)
    def metodo_nao_permitido(_):
        return erro(405, "METODO_NAO_PERMITIDO", "Use o método GET nesta rota")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=3000)
