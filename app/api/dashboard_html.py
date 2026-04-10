"""HTML do dashboard operacional do TA6000."""

from __future__ import annotations


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Painel TA6000</title>
  <link rel="stylesheet" href="/static/dashboard.css" />
</head>
<body>
  <main class="shell">
    <header class="topbar panel">
      <div class="topbar-copy">
        <p class="eyebrow">Monitoramento inteligente do compressor</p>
        <h1>COMPRESSOR TA6000</h1>
        <div class="hero-status" id="hero-status">Carregando status operacional...</div>
        <p class="hero-description" id="hero-description">
          O painel vai carregar a base completa do SQL quando disponivel e usar o CSV grande como contingencia analitica.
        </p>
      </div>
      <div class="topbar-meta">
        <button class="icon-button" id="refresh-button" type="button">Atualizar painel</button>
        <div class="meta-stack">
          <div class="meta-chip" id="badge-source">Fonte: --</div>
          <div class="meta-chip" id="badge-refresh">Atualizacao: --</div>
          <div class="meta-chip" id="badge-range">Cobertura: --</div>
          <div class="meta-chip" id="badge-rows">Leituras: --</div>
        </div>
      </div>
    </header>

    <section class="filter-panel panel">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Filtros uteis</p>
          <h2>Leitura operacional e analitica</h2>
        </div>
        <div class="panel-note">
          Troque subsistema, indicador, severidade e granularidade do grafico sem recarregar a pagina.
        </div>
      </div>

      <div class="subsystem-row" id="subsystem-pills"></div>

      <div class="filter-grid">
        <div class="field">
          <label for="signal-select">Indicador principal</label>
          <select id="signal-select"></select>
        </div>
        <div class="field">
          <label for="severity-select">Prioridade dos alertas</label>
          <select id="severity-select"></select>
        </div>
        <div class="field">
          <label for="search-input">Buscar alerta ou sinal</label>
          <input id="search-input" type="text" placeholder="titulo, regra, subsistema ou sinal" />
        </div>
        <div class="field">
          <label for="range-value">Janela do grafico</label>
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
          <label for="bucket-select">Agrupar serie temporal</label>
          <select id="bucket-select">
            <option value="raw">sem agrupamento</option>
            <option value="minutes" selected>por minuto</option>
            <option value="hours">por hora</option>
            <option value="days">por dia</option>
          </select>
        </div>
      </div>

      <div class="preset-row" id="preset-row"></div>
    </section>

    <section class="dashboard-grid">
      <section class="panel operational-panel">
        <div class="panel-heading">
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
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Scores</p>
            <h2>Risco por subsistema</h2>
          </div>
          <div class="panel-note">Clique em um mostrador para focar o painel.</div>
        </div>
        <div class="score-grid" id="score-grid"></div>
      </section>

      <section class="panel trend-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Evolucao no tempo</p>
            <h2 id="trend-title">Carregando tendencia...</h2>
          </div>
          <div class="panel-note" id="trend-subtitle">Aguardando a serie temporal</div>
        </div>
        <div class="chart-card" id="chart-card">
          <svg id="trend-chart" viewBox="0 0 960 430" preserveAspectRatio="none"></svg>
          <div class="chart-tooltip" id="chart-tooltip"></div>
        </div>
        <div class="legend-row">
          <span><i class="legend-line legend-actual"></i>Valor real</span>
          <span><i class="legend-line legend-target"></i>Linha de meta</span>
          <span><i class="legend-line legend-mean"></i>Media 15 min</span>
          <span><i class="legend-line legend-ewma"></i>EWMA</span>
          <span><i class="legend-dot legend-alert"></i>Eventos de alerta</span>
        </div>
        <div class="trend-summary-grid" id="trend-summary-grid"></div>
      </section>

      <section class="panel context-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Leitura amigavel</p>
            <h2>Resumo atual</h2>
          </div>
          <div class="panel-note">Valores resumidos da ultima amostra e regras do indicador.</div>
        </div>
        <div class="context-grid" id="context-grid"></div>
        <div class="stack-title">Meta e limites do indicador</div>
        <div class="stack-list scroll-area rules-area" id="rule-list"></div>
      </section>

      <section class="panel quality-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Qualidade</p>
            <h2>Observacoes da amostra</h2>
          </div>
          <div class="panel-note">Apontamentos de nulos, zeros anormais e sensores travados.</div>
        </div>
        <div class="stack-list scroll-area quality-area" id="quality-list"></div>
      </section>

      <section class="panel recent-alerts-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Historico</p>
            <h2>Eventos recentes</h2>
          </div>
          <div class="panel-note" id="recent-count">0 eventos</div>
        </div>
        <div class="stack-list scroll-area tall-area" id="recent-alert-list"></div>
      </section>

      <section class="panel active-alerts-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Agora</p>
            <h2>Alertas ativos</h2>
          </div>
          <div class="panel-note" id="active-count">0 alertas</div>
        </div>
        <div class="stack-list scroll-area tall-area" id="active-alert-list"></div>
      </section>

      <section class="panel explorer-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Mapa de sinais</p>
            <h2>Explorador do subsistema</h2>
          </div>
          <div class="panel-note" id="signal-panel-note">Selecione qualquer linha para trocar o grafico.</div>
        </div>
        <div class="signal-stack scroll-area explorer-area" id="signal-list"></div>
      </section>
    </section>
  </main>

  <script src="/static/dashboard.js" defer></script>
</body>
</html>
"""
