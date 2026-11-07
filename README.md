# API de Agregação de Dados Climáticos e Geográficos

Trabalho de **Técnicas de Integração de Sistemas (N703)**.

API REST em Python (Flask) que recebe o **nome de uma cidade brasileira** e devolve dados
geográficos e climáticos combinados, consumindo duas APIs públicas:

- **Open-Meteo** (geocodificação e previsão do tempo): https://open-meteo.com/en/docs
- **IBGE Localidades** (estados e municípios): https://servicodados.ibge.gov.br/api/docs/localidades

As coordenadas **não ficam fixas no código**: são obtidas dinamicamente a partir do nome da cidade.

**Escolha das APIs:** conforme a nota da proposta, que permite outras APIs públicas desde que a busca seja feita
pelo nome da cidade e as coordenadas sejam obtidas dinamicamente, usamos diretamente a **API oficial do IBGE**
(em vez da Brasil API - IBGE sugerida) e o **Open-Meteo**, incluindo o seu serviço de **geocodificação**, que
transforma o nome da cidade em latitude e longitude.

## Conceito do projeto: integração e enriquecimento de dados

O projeto junta **dados de duas APIs diferentes, que vêm de duas bases de dados diferentes**:

- a base de **localidades do IBGE** (estados e municípios do Brasil);
- a base **meteorológica e de geocodificação do Open-Meteo** (coordenadas e previsão do tempo).

No endpoint de clima, a informação de uma cidade é **enriquecida**: a cidade é localizada pelo nome, suas
coordenadas são usadas para buscar o clima, e o estado, que o Open-Meteo informa por extenso (por exemplo,
"Ceará"), é convertido na sigla oficial ("CE") consultando a base do IBGE. O resultado é uma
**nova API**, que entrega em uma única resposta o que antes exigiria consultar duas fontes separadas.
O endpoint de cidades por estado usa apenas a base do IBGE.

## Fluxo de integração

Exemplo com `GET /api/v1/clima/Fortaleza`:

| # | Etapa do fluxo | Onde acontece no código |
|---|----------------|-------------------------|
| 1 | Requisição do cliente, que informa o nome da cidade | O navegador ou o Postman faz o pedido `GET /api/v1/clima/Fortaleza` |
| 2 | Sua API recebe a requisição | `clima_da_cidade()` em `src/app.py` recebe o pedido e valida o nome (mínimo de 2 caracteres; senão, erro 400) |
| 3 | Busca os dados da cidade | `buscar_cidade()` em `src/openmeteo.py` consulta a geocodificação do Open-Meteo (somente cidades do Brasil) |
| 4 | Recebe os dados da cidade | Nome, estado por extenso, latitude e longitude. Se a cidade não existir, a API responde erro 404 |
| 5 | Requisita dados climáticos | `buscar_clima()` em `src/openmeteo.py` usa a latitude e a longitude recebidas para obter a previsão de hoje. Se o serviço falhar, a API responde erro 503 |
| 6 | Combina os dados (climáticos + geográficos) | Em `src/app.py`, o estado é convertido em sigla pelo IBGE (`buscar_sigla_estado()` em `src/ibge.py`), o código do tempo vira texto e tudo é reunido em um único JSON |
| 7 | Responde ao cliente | A API devolve o resultado combinado com HTTP 200 (ou o erro padronizado, se algo falhou no caminho) |

**Observação:** nas etapas 3 e 4, a busca da cidade e das coordenadas é feita pela geocodificação do Open-Meteo.
O IBGE entra na etapa 6, enriquecendo o resultado com a sigla oficial do estado. No endpoint
`/api/v1/cidades/{sigla_uf}`, o IBGE é a fonte principal dos dados.

## Integrantes

Veja [INTEGRANTES.md](INTEGRANTES.md).

### Contribuições dos integrantes

**Kelvin Jonathas Freitas do Nascimento (2415481)**

- Leu e conferiu a proposta da atividade seção por seção, verificando se o projeto atendia a cada requisito.
- Escolheu a linguagem do projeto (Python) e configurou o ambiente no Windows.
- Executou a API e os testes automatizados no próprio computador e organizou as pastas do repositório
  conforme a estrutura exigida.
- Testou todos os endpoints no navegador e no Postman, importando e executando a coleção, e analisou os
  resultados, incluindo casos de erro e nomes de cidade digitados de formas diferentes.

## Tecnologias

- **Python** (desenvolvido com a versão 3.12; requer 3.10 ou superior)
- **Flask**: framework web que define as rotas da API
- **flask-cors**: habilita o CORS
- **requests**: faz as chamadas às APIs externas
- **pytest**: testes automatizados
- **Postman**: exploração e teste manual da API

## Como executar

```bash
# 1. Instalar as dependências
pip install -r src/requirements.txt

# 2. Ligar a API (porta 3000)
python src/app.py
```

A API fica disponível em `http://localhost:3000`. É necessário acesso à internet, porque a API consulta
serviços externos.

## Como rodar os testes

```bash
python -m pytest
```

Os testes não usam a internet: as consultas externas são substituídas por versões simuladas.

## Endpoints

Todos os endpoints usam exclusivamente o método HTTP **GET** (consulta de dados, sem alterar nada).

### `GET /api/v1/health`

Verifica se a API está no ar. A resposta é sempre HTTP 200.

Funcionando normalmente:

```json
{ "status": "healthy", "versao": "1.0.0", "timestamp": "2026-11-01T14:30:00Z" }
```

Serviço degradado, quando uma consulta recente a um serviço externo (IBGE ou Open-Meteo) falhou:

```json
{
  "status": "degraded",
  "versao": "1.0.0",
  "timestamp": "2026-11-01T14:30:00Z",
  "motivo": "Serviço externo indisponível"
}
```

O health **não faz consultas novas** aos serviços externos (para continuar rápido e independente da internet):
ele apenas lembra o resultado das últimas consultas reais da API. A API volta a `healthy` assim que uma consulta
dá certo, ou após 1 minuto sem novas falhas.

### `GET /api/v1/clima/{nome_cidade}`

Devolve dados geográficos e o clima de hoje. O nome pode ser parcial.

Exemplo: `GET /api/v1/clima/Fortaleza`

```json
{
  "nome": "Fortaleza",
  "estado": "CE",
  "coordenadas": { "latitude": -3.71722, "longitude": -38.54306 },
  "clima": {
    "temperatura_min": 25.4,
    "temperatura_max": 31.3,
    "condicao": "Garoa Leve",
    "unidades": { "temperatura": "°C" }
  },
  "consultado_em": "2026-10-26T23:28:56Z"
}
```

### `GET /api/v1/cidades/{sigla_uf}?limite=N`

Lista as cidades de um estado em ordem alfabética.

Exemplo: `GET /api/v1/cidades/CE?limite=3`

```json
{
  "uf": "CE",
  "quantidade_retornada": 3,
  "cidades": [{ "nome": "Abaiara" }, { "nome": "Acarape" }, { "nome": "Acaraú" }],
  "consultado_em": "2026-10-26T23:23:12Z"
}
```

## Parâmetros

### Parâmetros da nossa API

| Parâmetro | Tipo | Endpoint | Obrigatório | Regra |
|-----------|------|----------|-------------|-------|
| `nome_cidade` | caminho (path) | `/clima/{nome_cidade}` | Sim | Pelo menos 2 caracteres; pode ser parcial |
| `sigla_uf` | caminho (path) | `/cidades/{sigla_uf}` | Sim | Exatamente 2 letras (ex.: `CE`) |
| `limite` | consulta (query) | `/cidades/{sigla_uf}` | Não | Inteiro de 1 a 100; padrão 10 |

### Parâmetros enviados às APIs externas

| API | Chamada | Parâmetros |
|-----|---------|------------|
| Open-Meteo (geocodificação) | `GET geocoding-api.open-meteo.com/v1/search` | `name`, `count=10`, `language=pt`, `country_code=BR`, `format=json` |
| Open-Meteo (previsão) | `GET api.open-meteo.com/v1/forecast` | `latitude`, `longitude`, `daily=weather_code,temperature_2m_max,temperature_2m_min`, `timezone=auto`, `forecast_days=1` |
| IBGE (municípios) | `GET .../localidades/estados/{UF}/municipios` | sigla da UF no caminho |
| IBGE (estados) | `GET .../localidades/estados` | nenhum |

## Erros

Todos os erros seguem o formato `{"erro": true, "codigo": "...", "mensagem": "...", ...}`.

| HTTP | Código | Quando acontece |
|------|--------|-----------------|
| 400 | `NOME_INVALIDO` | Nome da cidade com menos de 2 caracteres |
| 404 | `CIDADE_NAO_ENCONTRADA` | Nenhuma cidade brasileira com o nome informado |
| 400 | `SIGLA_UF_INVALIDA` | Sigla do estado que não tem exatamente 2 letras |
| 404 | `UF_NAO_ENCONTRADA` | Sigla com 2 letras, mas que não é um estado |
| 400 | `LIMITE_INVALIDO` | `limite` que não é um inteiro entre 1 e 100 |
| 503 | `SERVICO_EXTERNO_INDISPONIVEL` | Open-Meteo ou IBGE não respondeu |

## Estrutura do repositório

```
├── README.md
├── INTEGRANTES.md
├── src/
│   ├── app.py            # rotas da API e tratamento de erros
│   ├── openmeteo.py      # geocodificação e clima (Open-Meteo)
│   ├── ibge.py           # municípios e estados (IBGE)
│   ├── saude.py          # memória da saúde dos serviços externos (health "degraded")
│   └── requirements.txt  # dependências do projeto
├── tests/
│   ├── test_health.py
│   ├── test_cidades.py
│   └── test_clima.py
└── docs/
    └── postman_collection.json
```

## Coleção do Postman

O Postman foi usado como explorador de APIs para testar os endpoints. **O aprendizado do Postman ocorreu
a partir do segundo encontro virtual da disciplina.**

Importe `docs/postman_collection.json` no Postman (Import). A variável `baseUrl` já aponta para
`http://localhost:3000`. Com a API ligada, execute a coleção inteira para rodar todos os pedidos e
verificações.

## Uso de IA generativa

A equipe utilizou IA generativa neste trabalho.

- **Ferramenta:** Claude, da Anthropic (chat).
- **Etapas em que o Claude atuou:** geração do código-fonte da API (health check, endpoint de cidades por
  estado, endpoint de clima e tratamento de erros)
- **Etapas conduzidas pela equipe:** leitura e conferência da proposta item por item; definição dos requisitos
  e escolha da linguagem (Python); configuração do ambiente e organização das pastas do projeto; execução da
  API e dos testes no próprio computador; testes de todos os endpoints no navegador e no Postman, com análise
  dos resultados; e pedidos de ajustes e correções (por exemplo, o health "degraded", a estrutura do
  repositório e o conteúdo deste README).
- **Como professor:** a equipe também usou o Claude para aprender, fazendo perguntas para entender os
  conceitos do trabalho.

## Outras fontes de aprendizado

Além do Claude, a equipe buscou informações em **aulas no YouTube** e aprendeu a usar o Postman a partir do
segundo encontro virtual da disciplina.
