"""HTML do dashboard operacional do TA6000."""

from __future__ import annotations


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Painel TA6000</title>
  <link rel="stylesheet" href="/static/dashboard.css?v=20260415-ai-status-1" />
</head>
<body>
  <main class="shell">
    <header class="topbar panel">
      <div class="topbar-copy">
        <p class="eyebrow">Monitoramento analitico do compressor</p>
        <h1>TA6000</h1>
        <div class="hero-status" id="hero-status">Carregando status operacional...</div>
        <p class="hero-description" id="hero-description">
          O painel cruza a leitura principal, os alarmes e as correlacoes em uma visao unica e compacta.
        </p>
      </div>
      <div class="topbar-meta">
        <button class="icon-button" id="refresh-button" type="button">Atualizar</button>
        <div class="meta-grid">
          <div class="meta-chip" id="badge-source">Fonte: --</div>
          <div class="meta-chip" id="badge-refresh">Atualizacao: --</div>
          <div class="meta-chip" id="badge-range">Cobertura: --</div>
          <div class="meta-chip" id="badge-rows">Leituras: --</div>
          <div class="meta-chip" id="badge-ai">IA: --</div>
        </div>
      </div>
    </header>

    <section class="filter-panel panel">
      <div class="panel-heading compact-heading">
        <div>
          <p class="eyebrow">Filtros uteis</p>
          <h2>Foco rapido</h2>
        </div>
        <div class="panel-note">
          Escolha um ou mais indicadores e use o mesmo grafico para acompanhar tendencia e correlacao.
        </div>
      </div>

      <div class="subsystem-row" id="subsystem-pills"></div>

      <div class="filter-rail" id="filter-rail">
        <div class="field field-wide">
          <label for="signal-multiselect">Indicadores no grafico</label>
          <select id="signal-multiselect" multiple size="6"></select>
        </div>
        <div class="field">
          <label for="layer-select">Tipo de alerta</label>
          <select id="layer-select">
            <option value="all">todos</option>
            <option value="fixed_rule">fora da regra</option>
            <option value="trend">comportamento/tendencia anormal</option>
            <option value="operational_anomaly">anomalia operacional</option>
            <option value="predictive_statistics">risco antecipado</option>
          </select>
        </div>
        <div class="field">
          <label for="severity-select">Prioridade</label>
          <select id="severity-select"></select>
        </div>
        <div class="field field-search">
          <label for="search-input">Busca rapida</label>
          <input id="search-input" type="text" placeholder="titulo, regra, sinal ou subsistema" />
        </div>
        <div class="field field-inline">
          <label for="range-value">Janela</label>
          <div class="range-inline">
            <input id="range-value" type="number" min="1" max="5000" value="24" />
            <select id="range-unit">
              <option value="minutes">minutos</option>
              <option value="hours" selected>horas</option>
              <option value="days">dias</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label for="bucket-select">Agrupamento</label>
          <select id="bucket-select">
            <option value="raw">sem agrupamento</option>
            <option value="minutes" selected>por minuto</option>
            <option value="hours">por hora</option>
            <option value="days">por dia</option>
          </select>
        </div>
        <div class="field">
          <label for="chart-mode-select">Visual do grafico</label>
          <select id="chart-mode-select">
            <option value="real" selected>modo real</option>
            <option value="normalized">correlacao normalizada</option>
          </select>
        </div>
      </div>

      <div class="selection-bar">
        <div class="selection-chip-row" id="selected-signals"></div>
        <div class="preset-row" id="preset-row"></div>
      </div>
    </section>

    <section class="dashboard-grid">
      <section class="panel operational-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Operacao</p>
            <h2>Contexto do momento</h2>
          </div>
          <div class="panel-note" id="snapshot-ts">Ultima leitura: --</div>
        </div>
        <div class="status-strip" id="status-strip"></div>
        <div class="kpi-grid" id="hero-kpis"></div>
      </section>

      <section class="panel score-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Scores</p>
            <h2>Risco por subsistema</h2>
          </div>
          <div class="panel-note">Clique em um score para focar os sinais do subsistema.</div>
        </div>
        <div class="score-grid" id="score-grid"></div>
      </section>

      <section class="panel trend-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Grafico unico</p>
            <h2 id="trend-title">Carregando serie temporal...</h2>
          </div>
          <div class="panel-note" id="trend-subtitle">Aguardando o carregamento das curvas.</div>
        </div>
        <div class="chart-card" id="chart-card">
          <div class="chart-top-actions">
            <button class="chart-info-button" id="chart-info-button" type="button" aria-expanded="false" aria-controls="chart-info-panel">!</button>
          </div>
          <div class="chart-info-panel" id="chart-info-panel" hidden>
            <strong>Como ler o grafico</strong>
            <p><b>Modo real</b>: mostra os valores nas unidades originais de cada indicador. E bom para enxergar o comportamento fisico, mas pode dificultar comparacoes quando as grandezas usam unidades muito diferentes.</p>
            <p><b>Correlacao normalizada</b>: transforma cada serie para uma escala relativa de 0% a 100% dentro da janela atual. Isso ajuda a comparar a forma da curva, sem indicar percentual fisico real do processo.</p>
          </div>
          <svg id="trend-chart" viewBox="0 0 1040 380" preserveAspectRatio="none"></svg>
          <div class="chart-tooltip" id="chart-tooltip"></div>
        </div>
        <div class="legend-row" id="trend-legend"></div>
        <div class="trend-summary-grid" id="trend-summary-grid"></div>
      </section>

      <section class="panel context-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Leitura amigavel</p>
            <h2>Resumo do indicador</h2>
          </div>
          <div class="panel-note">Metas, limites e observacoes tecnicas do foco principal.</div>
        </div>
        <div class="context-grid" id="context-grid"></div>
        <div class="stack-block">
          <div class="stack-title">Regras aplicadas</div>
          <div class="stack-list scroll-area compact-area" id="rule-list"></div>
        </div>
        <div class="stack-block">
          <div class="stack-title">Qualidade de dado</div>
          <div class="stack-list scroll-area compact-area" id="quality-list"></div>
        </div>
      </section>

      <section class="panel active-alerts-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Agora</p>
            <h2>Alertas ativos</h2>
          </div>
          <div class="panel-note" id="active-count">0 alertas</div>
        </div>
        <div class="stack-list scroll-area alert-area" id="active-alert-list"></div>
      </section>

      <section class="panel recent-alerts-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Historico</p>
            <h2>Eventos recentes</h2>
          </div>
          <div class="panel-note" id="recent-count">0 eventos</div>
        </div>
        <div class="stack-list scroll-area alert-area" id="recent-alert-list"></div>
      </section>

      <section class="panel explorer-panel">
        <div class="panel-heading compact-heading">
          <div>
            <p class="eyebrow">Mapa de sinais</p>
            <h2>Explorador do subsistema</h2>
          </div>
          <div class="panel-note" id="signal-panel-note">Selecione um foco principal ou inclua no grafico.</div>
        </div>
        <div class="signal-stack scroll-area explorer-area" id="signal-list"></div>
      </section>
    </section>
  </main>

  <script src="/static/dashboard.js?v=20260415-ai-status-1" defer></script>
</body>
</html>
"""
