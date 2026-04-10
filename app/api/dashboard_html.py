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
        <p class="eyebrow">Monitoramento analitico do compressor</p>
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
          <p class="eyebrow">Filtros e correlacao</p>
          <h2>Leitura operacional limpa e navegavel</h2>
        </div>
        <div class="panel-note">
          Defina o foco principal, adicione outros indicadores para correlacionar e ajuste a janela sem recarregar a pagina.
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

      <div class="selection-bar">
        <div>
          <div class="stack-title compact-title">Indicadores no grafico</div>
          <div class="selection-chip-row" id="selected-signals"></div>
        </div>
        <div class="panel-note" id="selection-help">
          Clique em um sinal no explorador para focar e use o botao de correlacao para comparar ate 4 indicadores.
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

      <section class="panel diagnosis-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Prescricao</p>
            <h2>Leitura prescritiva</h2>
          </div>
          <div class="panel-note" id="diagnosis-caption">Aguardando um alerta com diagnostico prescritivo.</div>
        </div>
        <div class="diagnosis-score-grid" id="diagnosis-score-grid"></div>
        <div class="stack-title">Flags ativas</div>
        <div class="selection-chip-row flags-row" id="diagnosis-flags"></div>
        <div class="stack-title">Hipoteses ranqueadas</div>
        <div class="stack-list scroll-area diagnosis-area" id="diagnosis-hypotheses"></div>
        <div class="stack-title">Acoes recomendadas</div>
        <div class="stack-list scroll-area actions-area" id="diagnosis-actions"></div>
        <div class="stack-title">Observacoes</div>
        <div class="stack-list scroll-area observations-area" id="diagnosis-observations"></div>
      </section>

      <section class="panel trend-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Evolucao no tempo</p>
            <h2 id="trend-title">Carregando tendencia...</h2>
          </div>
          <div class="panel-note" id="trend-subtitle">Aguardando a serie temporal</div>
        </div>

        <div class="chart-toolbar">
          <div class="panel-note" id="trend-mode-note">Leitura principal com setpoint e limites operacionais.</div>
        </div>

        <div class="chart-card primary-chart-card" id="chart-card">
          <div class="chart-card-header">
            <div class="chart-card-title">Leitura principal</div>
            <div class="chart-card-note" id="primary-chart-note">Meta, limites e eventos do indicador em foco.</div>
          </div>
          <svg id="trend-chart" viewBox="0 0 960 430" preserveAspectRatio="none"></svg>
          <div class="chart-tooltip" id="chart-tooltip"></div>
        </div>
        <div class="legend-row" id="trend-legend"></div>
        <div class="trend-summary-grid" id="trend-summary-grid"></div>

        <div class="chart-card correlation-card">
          <div class="chart-card-header">
            <div class="chart-card-title">Correlacao entre indicadores</div>
            <div class="chart-card-note" id="correlation-subtitle">Adicione 2 ou mais indicadores para comparar o comportamento no tempo.</div>
          </div>
          <svg id="correlation-chart" viewBox="0 0 960 260" preserveAspectRatio="none"></svg>
          <div class="chart-tooltip" id="correlation-tooltip"></div>
        </div>
        <div class="legend-row" id="correlation-legend"></div>
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
          <div class="panel-note" id="signal-panel-note">Selecione um foco principal ou adicione sinais para correlacionar.</div>
        </div>
        <div class="signal-stack scroll-area explorer-area" id="signal-list"></div>
      </section>

      <section class="panel quality-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Qualidade de dado</p>
            <h2>Observacoes tecnicas da ultima amostra</h2>
          </div>
          <div class="panel-note">Sensores travados, zeros suspeitos, plausibilidade e nulos recentes.</div>
        </div>
        <div class="stack-list scroll-area quality-area" id="quality-list"></div>
      </section>
    </section>
  </main>

  <script src="/static/dashboard.js" defer></script>
</body>
</html>
"""
