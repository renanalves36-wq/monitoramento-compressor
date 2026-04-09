# TA6000 Monitor

Sistema em Python para monitoramento inteligente, alerta antecipado e apoio a predicao de falhas de um compressor industrial TA6000 com dados vindos do SQL Server.

## O que o projeto entrega

- Leitura incremental por `TimeStamp` usando `mssql-python`
- Fallback automatico para CSV de demonstracao quando o SQL Server nao estiver acessivel
- Query SQL com `SELECT` explicito, aliases amigaveis e tratamento de colunas com numero, `%` e acento
- Limpeza e validacao de dados: nulos, duplicidade temporal, ordenacao, tipos, sensores travados, zeros anormais e faixa plausivel
- Features estatisticas por modo operacional: medias moveis, desvio padrao, min/max, slope, z-score e EWMA
- Motor de alertas em tres camadas: regra fixa, tendencia e anomalia operacional
- Persistencia local de alertas em SQLite
- API FastAPI com snapshot atual, ultimas leituras, alertas ativos e score de risco por subsistema
- Estrutura pronta para evoluir depois para uma camada de explicacao com LLM

## Estrutura

```text
app/
  main.py
  config.py
  db/
    connection.py
    queries.py
  domain/
    mappings.py
    schemas.py
  services/
    ingestion_service.py
    feature_service.py
    alert_service.py
    health_service.py
  api/
    routes_status.py
    routes_alerts.py
  storage/
    alert_repository.py
  utils/
    logger.py
    datetime_utils.py
config/
  alert_rules.json
tests/
requirements.txt
.env.example
README.md
```

## Variaveis e subsistemas

- `ar_processo`: pressao, descarga, temperatura do 3o estagio e posicoes de valvula
- `lubrificacao`: pressao de oleo, temperatura do oleo, diferencial de filtro e vacuo da caixa de engrenagem
- `vibracao`: vibracoes por estagio e vibracao maxima
- `motor`: temperaturas de estator, rolamento dianteiro e corrente
- `operacao`: estados operacionais e contadores

## Como rodar no VS Code

1. Crie e ative um ambiente virtual com Python 3.11+.
2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Copie `.env.example` para `.env` e preencha as credenciais do SQL Server.
4. Inicie a API:

```bash
uvicorn app.main:app --reload
```

5. Acesse:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/status/current`
- `http://127.0.0.1:8000/status/readings`
- `http://127.0.0.1:8000/status/scores`
- `http://127.0.0.1:8000/alerts`

## Modos de fonte de dados

O projeto aceita tres modos em `DATA_SOURCE_MODE`:

- `auto`: tenta SQL Server e cai para CSV demo se a conexao falhar
- `sql`: usa apenas SQL Server
- `demo_csv`: usa apenas o arquivo CSV local

Para Codespaces ou qualquer ambiente sem acesso a rede interna da empresa, use:

```env
DATA_SOURCE_MODE=demo_csv
DEMO_CSV_PATH=data/demo_ta6000.csv
```

O arquivo de demonstracao ja vem no projeto em [demo_ta6000.csv](/c:/Users/011226939/Documents/Monitoramento%20compressor/data/demo_ta6000.csv).

## Configuracao do SQL Server

O projeto usa `mssql-python` e nao usa ODBC. A conexao pode ser configurada de duas formas:

- via `SQL_CONNECTION_STRING`
- ou montada automaticamente com `SQL_SERVER`, `SQL_PORT`, `SQL_DATABASE`, `SQL_USERNAME` e `SQL_PASSWORD`

Exemplo de string:

```text
Server=srv01win185,1433;Database=INDUSOFT;User Id=usuario;Password=senha;Encrypt=Optional;TrustServerCertificate=yes
```

Se o SQL Server nao puder ser acessado a partir do ambiente atual, a API continua operando em modo de demonstracao com CSV e persistencia de alertas em SQLite.

## Regras e calibracao

As regras iniciais estao em [config/alert_rules.json](/c:/Users/011226939/Documents/Monitoramento%20compressor/config/alert_rules.json). Elas cobrem:

- pressao de sistema
- corrente de motor
- temperatura e pressao de oleo
- vibracao por estagio
- vacuo da caixa de engrenagem
- temperaturas do motor
- tendencia por slope, z-score e desvio de EWMA
- anomalias operacionais como zero anormal e possivel inconsistencia de engenharia

O sinal `pv_pres_vacuo_cx_engran_inh2o` ja nasce com tratamento para possivel divergencia de unidade/escala, conforme observado na amostra.

## Endpoints

- `GET /status`: saude do servico e ultima atualizacao
- `GET /status`: inclui tambem a fonte de dados ativa em `data_source`
- `GET /status/current`: snapshot mais recente do compressor
- `GET /status/readings?limit=20`: ultimas leituras em ordem decrescente de tempo
- `GET /status/scores`: score de risco por subsistema
- `GET /alerts`: alertas ativos persistidos em SQLite

## Evolucao para IA explicativa

O sistema ja separa:

- contexto operacional
- snapshot atual
- features estatisticas
- alertas estruturados com severidade, camada e metadados
- scores por subsistema

Isso permite adicionar depois uma etapa de explicacao por LLM sem mudar a base de ingestao nem o motor de alertas.

## Testes

Os testes incluidos sao de sanidade e validam:

- ausencia de `SELECT *`
- aliases de colunas especiais
- disparo basico de regras fixas e anomalias

Execute com:

```bash
python -m unittest
```

## Demo rapida no Codespaces

Se o banco `srv01win185` nao for acessivel a partir do Codespace:

1. Ajuste o `.env`:

```env
DATA_SOURCE_MODE=demo_csv
DEMO_CSV_PATH=data/demo_ta6000.csv
```

2. Suba a API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Teste:

- `/status`
- `/status/current`
- `/status/readings`
- `/status/scores`
- `/alerts`
