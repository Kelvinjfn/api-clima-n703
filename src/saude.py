"""Memória simples sobre a saúde dos serviços externos (usada pelo /health).

Ideia: o /health NÃO faz consultas novas aos serviços externos (isso o deixaria
lento e dependente de internet). Ele apenas lembra o que aconteceu nas últimas
consultas reais que a API fez a pedido dos usuários.
"""
import time

# Uma falha só deixa a API como "degraded" por este tempo (em segundos).
# Se ninguém consultar nada depois disso, voltamos a "healthy" em vez de
# ficar marcado como degradado para sempre.
JANELA_SEGUNDOS = 60


class MonitorServicos:
    def __init__(self, relogio=time.monotonic):
        self._relogio = relogio  # relógio injetável: facilita simular o tempo nos testes
        self._ultima_falha = None
        self._ultimo_sucesso = None

    def registrar_falha(self):
        self._ultima_falha = self._relogio()

    def registrar_sucesso(self):
        self._ultimo_sucesso = self._relogio()

    def degradado(self):
        if self._ultima_falha is None:
            return False  # nunca houve falha
        if self._relogio() - self._ultima_falha > JANELA_SEGUNDOS:
            return False  # a falha é antiga demais
        if self._ultimo_sucesso is not None and self._ultimo_sucesso >= self._ultima_falha:
            return False  # já houve sucesso depois da falha: voltou ao normal
        return True
