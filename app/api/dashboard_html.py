"""HTML do dashboard operacional analitico do TA6000."""

from __future__ import annotations


PART_1 = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>TA6000 Analytical Dashboard</title>
  <style>
    :root {
      --bg-top: #f3efe3;
      --bg-bottom: #e4dccd;
      --panel: rgba(255, 250, 242, 0.86);
      --panel-strong: #fffdf8;
      --line: rgba(17, 35, 58, 0.12);
      --ink: #11233a;
      --muted: #5f6c7b;
      --teal: #0f766e;
      --teal-soft: rgba(15, 118, 110, 0.12);
      --gold: #d97706;
      --gold-soft: rgba(217, 119, 6, 0.12);
      --red: #b45309;
      --red-soft: rgba(180, 83, 9, 0.12);
      --critical: #8b1e1e;
      --critical-soft: rgba(139, 30, 30, 0.12);
      --shadow: 0 18px 46px rgba(17, 35, 58, 0.12);
      --radius: 26px;
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at 0% 0%, rgba(15, 118, 110, 0.18), transparent 30%),
        radial-gradient(circle at 100% 0%, rgba(217, 119, 6, 0.18), transparent 24%),
        linear-gradient(180deg, var(--bg-top), var(--bg-bottom));
      min-height: 100vh;
    }

    .shell {
      width: min(1520px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 22px 0 40px;
    }

    .hero {
      position: relative;
      overflow: hidden;
      border-radius: 34px;
      padding: 28px;
      background: linear-gradient(135deg, rgba(17, 35, 58, 0.97), rgba(15, 118, 110, 0.88));
      color: #fff6ea;
      box-shadow: var(--shadow);
    }

    .hero::before,
    .hero::after {
      content: "";
      position: absolute;
      border-radius: 50%;
      pointer-events: none;
    }

    .hero::before {
      width: 280px;
      height: 280px;
      right: -80px;
      top: -60px;
      background: rgba(217, 119, 6, 0.22);
      filter: blur(10px);
    }

    .hero::after {
      width: 200px;
      height: 200px;
      right: 90px;
      bottom: -90px;
      background: rgba(255, 255, 255, 0.08);
    }

    .hero-top {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
    }

    .hero h1 {
      margin: 0;
      font-size: clamp(2.2rem, 5vw, 4.4rem);
      letter-spacing: -0.05em;
      line-height: 0.96;
    }

    .hero p {
      margin: 12px 0 0;
      max-width: 880px;
      color: rgba(255, 246, 234, 0.82);
      font-size: 1.04rem;
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.55;
    }

    .hero-note {
      min-width: 220px;
      padding: 14px 16px;
      border-radius: 20px;
      background: rgba(255, 246, 234, 0.1);
      border: 1px solid rgba(255, 246, 234, 0.14);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.92rem;
      line-height: 1.45;
    }

    .badges,
    .chip-row,
    .window-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .badges { margin-top: 18px; }

    .badge,
    .chip,
    .window-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 9px 13px;
      border-radius: 999px;
      border: 1px solid transparent;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.9rem;
      font-weight: 600;
      transition: 140ms ease;
      cursor: pointer;
      user-select: none;
    }

    .badge {
      cursor: default;
      background: rgba(255, 246, 234, 0.1);
      color: #fff6ea;
      border-color: rgba(255, 246, 234, 0.12);
    }

    .chip,
    .window-button {
      background: rgba(17, 35, 58, 0.04);
      color: var(--ink);
      border-color: rgba(17, 35, 58, 0.06);
    }

    .chip:hover,
    .window-button:hover,
    select:hover,
    input:hover {
      transform: translateY(-1px);
      border-color: rgba(15, 118, 110, 0.34);
    }

    .chip.active,
    .window-button.active {
      background: linear-gradient(135deg, rgba(15, 118, 110, 0.18), rgba(217, 119, 6, 0.18));
      border-color: rgba(15, 118, 110, 0.48);
      box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.1);
    }

    .layout {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      margin-top: 18px;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
      padding: 20px;
    }

    .toolbar { grid-column: span 12; }
    .stats { grid-column: span 12; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 14px; }
    .chart-card { grid-column: span 8; }
    .insights-card { grid-column: span 4; }
    .signals-card { grid-column: span 5; }
    .alerts-card { grid-column: span 7; }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 14px;
      margin-bottom: 16px;
    }

    .eyebrow {
      margin: 0 0 8px;
      font-family: Arial, Helvetica, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.11em;
      font-size: 0.72rem;
      color: var(--muted);
    }

    h2, h3 {
      margin: 0;
      letter-spacing: -0.03em;
    }

    h2 { font-size: 1.55rem; }
    h3 { font-size: 1.08rem; }

    .subtext {
      color: var(--muted);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.5;
      font-size: 0.92rem;
    }

    .filters {
      display: grid;
      grid-template-columns: 1.2fr 1fr 0.9fr 0.9fr 1fr;
      gap: 12px;
      margin-bottom: 14px;
    }

    .filter {
      display: grid;
      gap: 8px;
    }

    .filter label {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.82rem;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    select,
    input {
      width: 100%;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      padding: 12px 14px;
      color: var(--ink);
      font-size: 0.98rem;
      font-family: Arial, Helvetica, sans-serif;
      outline: none;
      transition: 140ms ease;
    }

    select:focus,
    input:focus {
      border-color: rgba(15, 118, 110, 0.52);
      box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.08);
    }

    .stat {
      padding: 18px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.44);
      border: 1px solid rgba(17, 35, 58, 0.08);
    }

    .stat-value {
      margin: 0 0 6px;
      font-size: clamp(1.55rem, 2.9vw, 2.35rem);
      line-height: 1;
    }

    .stat-note {
      margin: 0;
      color: var(--muted);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.92rem;
      line-height: 1.45;
    }

    .chart-wrap {
      position: relative;
      border-radius: 24px;
      overflow: hidden;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.75), rgba(253, 247, 236, 0.84));
      border: 1px solid rgba(17, 35, 58, 0.08);
      min-height: 420px;
      padding: 12px;
    }

    svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-top: 14px;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.9rem;
      color: var(--muted);
    }

    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    .legend-swatch {
      width: 28px;
      height: 4px;
      border-radius: 999px;
    }
"""
PART_2 = """
    .summary-grid,
    .snapshot-grid,
    .quality-list,
    .rules-list,
    .signal-list,
    .alerts-list,
    .risk-grid {
      display: grid;
      gap: 12px;
    }

    .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 16px; }
    .snapshot-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .risk-grid { margin-top: 14px; }

    .mini,
    .signal-item,
    .alert-item,
    .risk-item,
    .rule-item,
    .quality-item {
      background: var(--panel-strong);
      border: 1px solid rgba(17, 35, 58, 0.08);
      border-radius: 18px;
      padding: 14px;
    }

    .mini strong,
    .signal-label,
    .rule-title {
      display: block;
      margin-bottom: 6px;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.84rem;
      color: var(--muted);
      font-weight: 700;
    }

    .mini span,
    .signal-value {
      font-size: 1.08rem;
    }

    .risk-item {
      cursor: pointer;
      transition: 140ms ease;
    }

    .risk-item:hover,
    .signal-item:hover,
    .alert-item:hover {
      transform: translateY(-2px);
      border-color: rgba(15, 118, 110, 0.24);
    }

    .risk-item.active,
    .signal-item.active {
      border-color: rgba(15, 118, 110, 0.5);
      box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.14);
      background: linear-gradient(180deg, rgba(15, 118, 110, 0.06), rgba(255, 253, 248, 1));
    }

    .risk-top,
    .signal-top,
    .alert-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 8px;
    }

    .risk-bar {
      width: 100%;
      height: 11px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(17, 35, 58, 0.08);
      margin: 10px 0 8px;
    }

    .risk-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #1f7a4d, #d97706, #b45309, #8b1e1e);
    }

    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      white-space: nowrap;
    }

    .sev-low { background: var(--teal-soft); color: var(--teal); }
    .sev-medium { background: var(--gold-soft); color: var(--gold); }
    .sev-high { background: var(--red-soft); color: var(--red); }
    .sev-critical { background: var(--critical-soft); color: var(--critical); }
    .sev-all { background: rgba(17, 35, 58, 0.08); color: var(--ink); }

    .signal-item {
      cursor: pointer;
      transition: 140ms ease;
    }

    .signal-meta,
    .alert-meta,
    .quality-meta,
    .rule-meta,
    .empty {
      color: var(--muted);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.88rem;
      line-height: 1.5;
    }

    .signal-item small {
      font-family: Arial, Helvetica, sans-serif;
      color: var(--muted);
      font-size: 0.82rem;
    }

    .tooltip {
      position: absolute;
      pointer-events: none;
      transform: translate(-50%, calc(-100% - 12px));
      min-width: 180px;
      max-width: 240px;
      padding: 10px 12px;
      border-radius: 16px;
      background: rgba(17, 35, 58, 0.96);
      color: #fff6ea;
      border: 1px solid rgba(255, 246, 234, 0.12);
      box-shadow: 0 14px 36px rgba(0, 0, 0, 0.2);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.85rem;
      line-height: 1.45;
      opacity: 0;
      transition: opacity 120ms ease;
    }

    .tooltip.visible { opacity: 1; }

    .empty {
      padding: 18px;
      border-radius: 18px;
      border: 1px dashed rgba(17, 35, 58, 0.16);
      background: rgba(255, 255, 255, 0.48);
    }

    @media (max-width: 1280px) {
      .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .chart-card, .insights-card, .signals-card, .alerts-card { grid-column: span 12; }
      .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    @media (max-width: 860px) {
      .shell { width: min(100vw - 16px, 1520px); }
      .hero { padding: 22px; }
      .hero-top { flex-direction: column; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .summary-grid, .snapshot-grid { grid-template-columns: 1fr; }
      .filters { grid-template-columns: 1fr; }
    }

    @media (max-width: 560px) {
      .stats { grid-template-columns: 1fr; }
      .card { padding: 16px; border-radius: 20px; }
      .chart-wrap { min-height: 340px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1>TA6000 Analytical Cockpit</h1>
          <p>Visualizacao operacional com leitura analitica do compressor, filtros interativos, graficos temporais com linha de meta e navegacao por subsistema pensada para investigacao rapida.</p>
        </div>
        <div class="hero-note">
          Clique em um subsistema, depois em um sinal, e o painel atualiza sem recarregar a pagina. A linha dourada mostra a meta ou o setpoint; a banda suave mostra os limites operacionais quando existirem.
        </div>
      </div>
      <div class="badges">
        <div class="badge" id="service-status">Status: carregando...</div>
        <div class="badge" id="data-source">Fonte: --</div>
        <div class="badge" id="last-refresh">Atualizacao: --</div>
        <div class="badge" id="active-selection">Sinal: --</div>
      </div>
    </section>

    <section class="layout">
      <section class="card toolbar">
        <div class="card-header">
          <div>
            <p class="eyebrow">Controles</p>
            <h2>Filtros e Navegacao</h2>
          </div>
          <div class="subtext">O painel preserva o contexto do clique atual e faz atualizacao incremental a cada 30 segundos.</div>
        </div>
        <div class="chip-row" id="subsystem-chips"></div>
        <div class="filters">
          <div class="filter">
            <label for="signal-select">Sinal monitorado</label>
            <select id="signal-select"></select>
          </div>
          <div class="filter">
            <label for="severity-select">Severidade dos alertas</label>
            <select id="severity-select"></select>
          </div>
          <div class="filter">
            <label for="alert-search">Busca rapida</label>
            <input id="alert-search" type="text" placeholder="filtrar titulo, regra ou subsistema" />
          </div>
          <div class="filter">
            <label>Janela temporal</label>
            <div class="window-buttons" id="window-buttons"></div>
          </div>
          <div class="filter">
            <label for="refresh-button">Comando</label>
            <button class="window-button" id="refresh-button" type="button">Atualizar agora</button>
          </div>
        </div>
      </section>

      <section class="stats">
        <article class="stat"><p class="eyebrow">Alertas ativos</p><h3 class="stat-value" id="metric-alerts">--</h3><p class="stat-note">Alertas apos filtros aplicados</p></article>
        <article class="stat"><p class="eyebrow">Maior risco</p><h3 class="stat-value" id="metric-top-risk">--</h3><p class="stat-note" id="metric-top-risk-label">Sem score</p></article>
        <article class="stat"><p class="eyebrow">Valor atual</p><h3 class="stat-value" id="metric-current-value">--</h3><p class="stat-note" id="metric-current-unit">Sinal selecionado</p></article>
        <article class="stat"><p class="eyebrow">Meta atual</p><h3 class="stat-value" id="metric-target-value">--</h3><p class="stat-note" id="metric-target-label">Meta / setpoint</p></article>
        <article class="stat"><p class="eyebrow">Desvio</p><h3 class="stat-value" id="metric-delta">--</h3><p class="stat-note">Variacao do ultimo ponto</p></article>
        <article class="stat"><p class="eyebrow">Slope 15 min</p><h3 class="stat-value" id="metric-slope">--</h3><p class="stat-note">Tendencia recente</p></article>
      </section>

      <section class="card chart-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Serie Temporal</p>
            <h2 id="trend-title">Carregando tendencia...</h2>
          </div>
          <div class="subtext" id="trend-subtitle">Aguardando serie temporal</div>
        </div>
        <div class="chart-wrap" id="chart-wrap">
          <svg id="trend-chart" viewBox="0 0 920 420" preserveAspectRatio="none"></svg>
          <div class="tooltip" id="chart-tooltip"></div>
        </div>
        <div class="legend">
          <div class="legend-item"><span class="legend-swatch" style="background:#0f766e"></span>Valor real</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#d97706"></span>Linha de meta</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#11233a"></span>Media 15 min</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#b45309"></span>EWMA</div>
        </div>
        <div class="summary-grid" id="trend-summary"></div>
      </section>

      <section class="card insights-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Contexto</p>
            <h2>Leitura Operacional</h2>
          </div>
          <div class="subtext" id="snapshot-timestamp">--</div>
        </div>
        <div class="snapshot-grid" id="snapshot-grid"></div>
        <div class="card-header" style="margin-top:18px;"><div><p class="eyebrow">Qualidade</p><h3>Ultimos apontamentos</h3></div></div>
        <div class="quality-list" id="quality-list"></div>
        <div class="card-header" style="margin-top:18px;"><div><p class="eyebrow">Regras associadas</p><h3>Meta, limites e criterios</h3></div></div>
        <div class="rules-list" id="rules-list"></div>
      </section>
"""
PART_3 = """
      <section class="card signals-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Navegacao por Sinal</p>
            <h2>Matriz do Subsistema</h2>
          </div>
          <div class="subtext" id="signals-subtitle">Clique em um sinal para atualizar o grafico</div>
        </div>
        <div class="risk-grid" id="risk-grid"></div>
        <div class="signal-list" id="signal-list" style="margin-top:16px;"></div>
      </section>

      <section class="card alerts-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Alertas</p>
            <h2>Fila Analitica</h2>
          </div>
          <div class="subtext">Filtragem instantanea por severidade, subsistema e texto.</div>
        </div>
        <div class="alerts-list" id="alerts-list"></div>
      </section>
    </section>
  </main>

  <script>
    const state = {
      catalog: null,
      status: null,
      snapshot: null,
      scores: [],
      alerts: [],
      trend: null,
      subsystem: "all",
      severity: "all",
      signal: null,
      window: 120,
      search: "",
      chartPoints: []
    };

    const windowOptions = [30, 60, 120, 240];
    const snapshotKeys = [
      ["st_oper", "Estado operacional"],
      ["st_carga_oper", "Estado de carga"],
      ["mode_key", "Modo atual"],
      ["ds_turno", "Turno"],
      ["status", "Status"],
      ["st_plc", "PLC"],
      ["pv_pres_sistema_bar", "Pressao sistema"],
      ["pv_corr_motor_a", "Corrente motor"]
    ];

    function formatNumber(value, digits = 2) {
      if (value === null || value === undefined || value === "") return "--";
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return String(value);
      return numeric.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }

    function formatMaybe(value, unit = "") {
      if (value === null || value === undefined || value === "") return "--";
      return `${formatNumber(value)}${unit ? " " + unit : ""}`;
    }

    function formatDate(value) {
      if (!value) return "--";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString("pt-BR");
    }

    function formatShortDate(value) {
      if (!value) return "--";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    }

    function severityClass(severity) {
      return `sev-${String(severity || "all").toLowerCase()}`;
    }

    function safeArray(value) {
      return Array.isArray(value) ? value : [];
    }

    function getVisibleSignals() {
      const signals = safeArray(state.catalog?.signals);
      if (state.subsystem === "all") return signals;
      return signals.filter((item) => item.subsystem === state.subsystem);
    }

    function getSelectedSignalMeta() {
      return safeArray(state.catalog?.signals).find((item) => item.signal === state.signal) || null;
    }

    function getFilteredAlerts() {
      return safeArray(state.alerts).filter((alert) => {
        const matchesSubsystem = state.subsystem === "all" || alert.subsystem === state.subsystem;
        const matchesSeverity = state.severity === "all" || alert.severity === state.severity;
        const haystack = `${alert.title} ${alert.rule_id} ${alert.subsystem} ${alert.signal || ""}`.toLowerCase();
        const matchesSearch = !state.search || haystack.includes(state.search.toLowerCase());
        return matchesSubsystem && matchesSeverity && matchesSearch;
      });
    }

    function ensureSignalSelection() {
      const visibleSignals = getVisibleSignals();
      if (!visibleSignals.length) {
        state.signal = null;
        return;
      }
      if (visibleSignals.some((item) => item.signal === state.signal)) return;
      const preferred = visibleSignals.find((item) => item.active_alerts > 0);
      state.signal = preferred ? preferred.signal : visibleSignals[0].signal;
    }

    function buildWindowButtons() {
      const container = document.getElementById("window-buttons");
      container.innerHTML = windowOptions.map((windowValue) => `
        <button class="window-button ${state.window === windowValue ? "active" : ""}" data-window="${windowValue}" type="button">
          ${windowValue} pontos
        </button>
      `).join("");
      container.querySelectorAll("[data-window]").forEach((button) => {
        button.addEventListener("click", async () => {
          state.window = Number(button.dataset.window);
          buildWindowButtons();
          await loadTrend();
        });
      });
    }

    function renderSubsystemChips() {
      const container = document.getElementById("subsystem-chips");
      const subsystems = ["all", ...safeArray(state.catalog?.subsystems)];
      container.innerHTML = subsystems.map((subsystem) => `
        <button class="chip ${state.subsystem === subsystem ? "active" : ""}" data-subsystem="${subsystem}" type="button">
          ${subsystem === "all" ? "Todos os subsistemas" : subsystem}
        </button>
      `).join("");
      container.querySelectorAll("[data-subsystem]").forEach((button) => {
        button.addEventListener("click", async () => {
          state.subsystem = button.dataset.subsystem;
          ensureSignalSelection();
          renderSubsystemChips();
          populateSignalSelect();
          renderRiskGrid();
          renderSignalList();
          renderAlerts();
          await loadTrend();
        });
      });
    }

    function populateSignalSelect() {
      const select = document.getElementById("signal-select");
      const signals = getVisibleSignals();
      select.innerHTML = signals.map((item) => `
        <option value="${item.signal}" ${item.signal === state.signal ? "selected" : ""}>
          ${item.label} (${item.signal})
        </option>
      `).join("");
    }

    function populateSeveritySelect() {
      const select = document.getElementById("severity-select");
      const severities = safeArray(state.catalog?.severities);
      select.innerHTML = severities.map((severity) => `
        <option value="${severity}" ${severity === state.severity ? "selected" : ""}>${severity}</option>
      `).join("");
    }

    function renderHeader() {
      document.getElementById("service-status").textContent = `Status: ${state.status?.service_status || "--"}`;
      document.getElementById("data-source").textContent = `Fonte: ${state.status?.data_source || "--"}`;
      document.getElementById("last-refresh").textContent = `Atualizacao: ${formatDate(state.status?.last_refresh_at)}`;
      document.getElementById("active-selection").textContent = `Sinal: ${getSelectedSignalMeta()?.label || "--"}`;
    }

    function renderMetrics() {
      const filteredAlerts = getFilteredAlerts();
      const scorePool = state.subsystem === "all"
        ? safeArray(state.scores)
        : safeArray(state.scores).filter((item) => item.subsystem === state.subsystem);
      const topScore = scorePool[0];
      const summary = state.trend?.summary || {};
      const signalMeta = getSelectedSignalMeta();
      const unit = signalMeta?.unit || state.trend?.unit || "";
      document.getElementById("metric-alerts").textContent = String(filteredAlerts.length);
      document.getElementById("metric-top-risk").textContent = topScore ? formatNumber(topScore.score, 1) : "--";
      document.getElementById("metric-top-risk-label").textContent = topScore ? topScore.subsystem : "Sem score";
      document.getElementById("metric-current-value").textContent = formatMaybe(summary.latest, unit);
      document.getElementById("metric-current-unit").textContent = signalMeta?.label || "Sinal selecionado";
      document.getElementById("metric-target-value").textContent = formatMaybe(summary.target_current ?? state.trend?.target_value, unit);
      document.getElementById("metric-target-label").textContent = state.trend?.target_label || "Meta / setpoint";
      document.getElementById("metric-delta").textContent = formatMaybe(summary.delta, unit);
      document.getElementById("metric-slope").textContent = formatMaybe(summary.slope_15m, unit ? `${unit}/min` : "");
    }

    function renderTrendSummary() {
      const container = document.getElementById("trend-summary");
      const summary = state.trend?.summary || {};
      const unit = state.trend?.unit || "";
      const items = [
        ["Media da janela", formatMaybe(summary.mean, unit)],
        ["Minimo", formatMaybe(summary.minimum, unit)],
        ["Maximo", formatMaybe(summary.maximum, unit)],
        ["Slope 1h", formatMaybe(summary.slope_1h, unit ? `${unit}/min` : "")],
        ["Z-score 1h", formatMaybe(summary.zscore_1h)],
        ["Desvio padrao 1h", formatMaybe(summary.std_1h, unit)]
      ];
      container.innerHTML = items.map(([label, value]) => `<div class="mini"><strong>${label}</strong><span>${value}</span></div>`).join("");
    }

    function renderSnapshot() {
      const container = document.getElementById("snapshot-grid");
      const values = state.snapshot?.values || {};
      document.getElementById("snapshot-timestamp").textContent = formatDate(state.snapshot?.timestamp);
      container.innerHTML = snapshotKeys.map(([key, label]) => `
        <div class="mini">
          <strong>${label}</strong>
          <span>${values[key] ?? state.snapshot?.[key] ?? "--"}</span>
        </div>
      `).join("");
    }

    function renderQuality() {
      const container = document.getElementById("quality-list");
      const issues = safeArray(state.snapshot?.data_quality_issues);
      container.innerHTML = issues.length
        ? issues.map((issue) => `<div class="quality-item"><div class="rule-title">${issue.issue_type}</div><div class="quality-meta">${issue.signal || "geral"} | ${issue.message}</div></div>`).join("")
        : '<div class="empty">Nenhum apontamento de qualidade na ultima amostra.</div>';
    }
"""
PART_4 = """
    function renderRules() {
      const container = document.getElementById("rules-list");
      const rules = safeArray(state.trend?.rules);
      container.innerHTML = rules.length
        ? rules.map((rule) => `
            <div class="rule-item">
              <div class="risk-top">
                <div>
                  <div class="rule-title">${rule.title}</div>
                  <div class="rule-meta">${rule.rule_id} | ${rule.layer}</div>
                </div>
                <span class="pill ${severityClass(rule.severity)}">${rule.severity}</span>
              </div>
              <div class="rule-meta">${rule.condition || "--"} ${rule.threshold || ""}</div>
            </div>
          `).join("")
        : '<div class="empty">Sem regras associadas ao sinal atual.</div>';
    }

    function renderRiskGrid() {
      const container = document.getElementById("risk-grid");
      container.innerHTML = safeArray(state.scores).map((item) => `
        <div class="risk-item ${state.subsystem === item.subsystem ? "active" : ""}" data-risk="${item.subsystem}">
          <div class="risk-top">
            <div><div class="signal-label">${item.subsystem}</div><div>${formatNumber(item.score, 1)}</div></div>
            <span class="pill ${severityClass(item.highest_severity || "all")}">${item.highest_severity || "none"}</span>
          </div>
          <div class="risk-bar"><div class="risk-fill" style="width:${Math.min(100, item.score)}%"></div></div>
          <div class="signal-meta">Alertas: ${item.active_alerts}</div>
        </div>
      `).join("");
      container.querySelectorAll("[data-risk]").forEach((element) => {
        element.addEventListener("click", async () => {
          state.subsystem = element.dataset.risk;
          ensureSignalSelection();
          renderSubsystemChips();
          populateSignalSelect();
          renderRiskGrid();
          renderSignalList();
          renderAlerts();
          await loadTrend();
        });
      });
    }

    function renderSignalList() {
      const container = document.getElementById("signal-list");
      const visibleSignals = getVisibleSignals();
      document.getElementById("signals-subtitle").textContent = state.subsystem === "all"
        ? "Todos os sinais disponiveis, com destaque para os que possuem alerta."
        : `Sinais do subsistema ${state.subsystem}. Clique em qualquer linha para trocar o grafico.`;
      if (!visibleSignals.length) {
        container.innerHTML = '<div class="empty">Nenhum sinal disponivel nesse filtro.</div>';
        return;
      }
      const values = state.snapshot?.values || {};
      container.innerHTML = visibleSignals.map((item) => `
        <div class="signal-item ${state.signal === item.signal ? "active" : ""}" data-signal="${item.signal}">
          <div class="signal-top">
            <div><div class="signal-label">${item.label}</div><div class="signal-value">${formatMaybe(values[item.signal], item.unit)}</div></div>
            <span class="pill ${item.active_alerts ? "sev-high" : "sev-all"}">${item.active_alerts} alertas</span>
          </div>
          <div class="signal-meta">Meta: ${formatMaybe(item.target_value, item.unit)} | Limites: ${formatMaybe(item.lower_limit, item.unit)} a ${formatMaybe(item.upper_limit, item.unit)}</div>
          <small>${item.signal}</small>
        </div>
      `).join("");
      container.querySelectorAll("[data-signal]").forEach((element) => {
        element.addEventListener("click", async () => {
          state.signal = element.dataset.signal;
          populateSignalSelect();
          renderSignalList();
          await loadTrend();
        });
      });
    }

    function renderAlerts() {
      const container = document.getElementById("alerts-list");
      const alerts = getFilteredAlerts();
      container.innerHTML = alerts.length
        ? alerts.map((alert) => `
            <div class="alert-item" data-alert-signal="${alert.signal || ""}" data-alert-subsystem="${alert.subsystem}">
              <div class="alert-top">
                <div><div class="signal-label">${alert.title}</div><div class="alert-meta">${alert.subsystem} | ${alert.signal || "--"} | ${alert.rule_id}</div></div>
                <span class="pill ${severityClass(alert.severity)}">${alert.severity}</span>
              </div>
              <div class="subtext">${alert.message}</div>
              <div class="alert-meta">Valor atual: ${formatMaybe(alert.current_value)} | Modo: ${alert.mode_key}</div>
              <div class="alert-meta">Ultima ocorrencia: ${formatDate(alert.last_seen_at)}</div>
            </div>
          `).join("")
        : '<div class="empty">Nenhum alerta corresponde aos filtros atuais.</div>';

      container.querySelectorAll("[data-alert-signal]").forEach((element) => {
        element.addEventListener("click", async () => {
          const signal = element.dataset.alertSignal;
          const subsystem = element.dataset.alertSubsystem;
          if (!signal) return;
          state.subsystem = subsystem || state.subsystem;
          state.signal = signal;
          ensureSignalSelection();
          renderSubsystemChips();
          populateSignalSelect();
          renderRiskGrid();
          renderSignalList();
          renderAlerts();
          await loadTrend();
        });
      });
    }

    function chartY(value, minValue, maxValue, plotTop, plotHeight) {
      if (maxValue === minValue) return plotTop + plotHeight / 2;
      const normalized = (value - minValue) / (maxValue - minValue);
      return plotTop + plotHeight - normalized * plotHeight;
    }

    function buildPath(points) {
      return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
    }

    function createTooltipContent(point, unit, targetLabel) {
      return `
        <div><strong>${formatDate(point.timestamp)}</strong></div>
        <div>Valor: ${formatMaybe(point.value, unit)}</div>
        <div>Media 15 min: ${formatMaybe(point.rolling_mean, unit)}</div>
        <div>EWMA: ${formatMaybe(point.ewma, unit)}</div>
        <div>${targetLabel || "Meta"}: ${formatMaybe(point.target_value, unit)}</div>
      `;
    }

    function renderChart() {
      const svg = document.getElementById("trend-chart");
      const tooltip = document.getElementById("chart-tooltip");
      const trend = state.trend;
      const points = safeArray(trend?.points);
      const title = document.getElementById("trend-title");
      const subtitle = document.getElementById("trend-subtitle");
      const unit = trend?.unit || "";
      if (!points.length) {
        svg.innerHTML = "";
        title.textContent = "Sem dados suficientes para o sinal atual";
        subtitle.textContent = "Aguardando serie temporal";
        return;
      }

      title.textContent = `${trend.label} (${trend.signal})`;
      subtitle.textContent = `${trend.subsystem} | ${points.length} pontos | ultima amostra ${formatDate(points[points.length - 1].timestamp)}`;
      const values = [];
      points.forEach((point) => {
        [point.value, point.target_value, point.rolling_mean, point.ewma, point.lower_limit, point.upper_limit].forEach((value) => {
          if (value !== null && value !== undefined && Number.isFinite(Number(value))) values.push(Number(value));
        });
      });
      if (!values.length) {
        svg.innerHTML = "";
        title.textContent = `${trend.label} (${trend.signal})`;
        subtitle.textContent = "Sem valores numericos suficientes na janela selecionada";
        return;
      }
      const rawMin = Math.min(...values);
      const rawMax = Math.max(...values);
      const padding = rawMax === rawMin ? Math.abs(rawMax || 1) * 0.2 : (rawMax - rawMin) * 0.12;
      const minValue = rawMin - padding;
      const maxValue = rawMax + padding;
      const width = 920;
      const height = 420;
      const margin = { top: 22, right: 22, bottom: 42, left: 72 };
      const plotWidth = width - margin.left - margin.right;
      const plotHeight = height - margin.top - margin.bottom;

      const chartPoints = points.map((point, index) => ({
        ...point,
        x: margin.left + (index / Math.max(points.length - 1, 1)) * plotWidth,
        y: chartY(Number(point.value ?? rawMin), minValue, maxValue, margin.top, plotHeight),
        meanY: point.rolling_mean === null || point.rolling_mean === undefined ? null : chartY(Number(point.rolling_mean), minValue, maxValue, margin.top, plotHeight),
        ewmaY: point.ewma === null || point.ewma === undefined ? null : chartY(Number(point.ewma), minValue, maxValue, margin.top, plotHeight),
        targetY: point.target_value === null || point.target_value === undefined ? null : chartY(Number(point.target_value), minValue, maxValue, margin.top, plotHeight)
      }));

      const actualPath = buildPath(chartPoints.map((point) => ({ x: point.x, y: point.y })));
      const meanPath = buildPath(chartPoints.filter((point) => point.meanY !== null).map((point) => ({ x: point.x, y: point.meanY })));
      const ewmaPath = buildPath(chartPoints.filter((point) => point.ewmaY !== null).map((point) => ({ x: point.x, y: point.ewmaY })));
      const targetPath = buildPath(chartPoints.filter((point) => point.targetY !== null).map((point) => ({ x: point.x, y: point.targetY })));

      const gridLines = [];
      for (let step = 0; step <= 4; step += 1) {
        const y = margin.top + (plotHeight / 4) * step;
        const value = maxValue - ((maxValue - minValue) / 4) * step;
        gridLines.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" stroke="rgba(17,35,58,0.08)" stroke-dasharray="4 8" /><text x="${margin.left - 12}" y="${y + 4}" fill="rgba(95,108,123,0.95)" font-size="12" text-anchor="end" font-family="Arial, Helvetica, sans-serif">${formatNumber(value)}</text>`);
      }

      const xLabels = [chartPoints[0], chartPoints[Math.floor((chartPoints.length - 1) / 2)], chartPoints[chartPoints.length - 1]];
      const xAxisLabels = xLabels.map((point) => `<text x="${point.x}" y="${height - 12}" fill="rgba(95,108,123,0.95)" font-size="12" text-anchor="middle" font-family="Arial, Helvetica, sans-serif">${formatShortDate(point.timestamp)}</text>`).join("");

      let bandMarkup = "";
      if (chartPoints[0].lower_limit !== null && chartPoints[0].upper_limit !== null) {
        const bandTop = chartY(Number(chartPoints[0].upper_limit), minValue, maxValue, margin.top, plotHeight);
        const bandBottom = chartY(Number(chartPoints[0].lower_limit), minValue, maxValue, margin.top, plotHeight);
        bandMarkup = `<rect x="${margin.left}" y="${bandTop}" width="${plotWidth}" height="${bandBottom - bandTop}" fill="rgba(15,118,110,0.08)" rx="18" />`;
      }

      svg.innerHTML = `
        <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" />
        ${bandMarkup}
        ${gridLines.join("")}
        <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(17,35,58,0.18)" />
        <path d="${targetPath}" fill="none" stroke="#d97706" stroke-width="2.4" stroke-dasharray="10 8" stroke-linecap="round" />
        <path d="${meanPath}" fill="none" stroke="#11233a" stroke-width="2.2" stroke-linecap="round" />
        <path d="${ewmaPath}" fill="none" stroke="#b45309" stroke-width="2.2" stroke-dasharray="8 6" stroke-linecap="round" />
        <path d="${actualPath}" fill="none" stroke="#0f766e" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round" />
        <circle cx="${chartPoints[chartPoints.length - 1].x}" cy="${chartPoints[chartPoints.length - 1].y}" r="5.5" fill="#0f766e" />
        ${xAxisLabels}
      `;

      svg.onmouseleave = () => tooltip.classList.remove("visible");
      svg.onmousemove = (event) => {
        const bounds = svg.getBoundingClientRect();
        const relativeX = ((event.clientX - bounds.left) / bounds.width) * width;
        const nearest = chartPoints.reduce((best, point) => {
          const currentDistance = Math.abs(point.x - relativeX);
          return (!best || currentDistance < best.distance) ? { distance: currentDistance, point } : best;
        }, null);
        if (!nearest) return;
        tooltip.innerHTML = createTooltipContent(nearest.point, unit, trend.target_label);
        tooltip.style.left = `${event.clientX - bounds.left}px`;
        tooltip.style.top = `${event.clientY - bounds.top}px`;
        tooltip.classList.add("visible");
      };
    }

    async function loadTrend() {
      if (!state.signal) return;
      const response = await fetch(`/status/trend?signal=${encodeURIComponent(state.signal)}&limit=${state.window}`);
      state.trend = await response.json();
      if (state.trend?.summary) {
        const points = safeArray(state.trend.points);
        state.trend.summary.target_current = points.length ? points[points.length - 1].target_value : state.trend.target_value;
      }
      renderHeader();
      renderMetrics();
      renderTrendSummary();
      renderRules();
      renderChart();
    }

    async function loadBaseData() {
      const [catalogRes, statusRes, snapshotRes, scoresRes, alertsRes] = await Promise.all([
        fetch("/status/catalog"),
        fetch("/status"),
        fetch("/status/current"),
        fetch("/status/scores"),
        fetch("/alerts")
      ]);
      state.catalog = await catalogRes.json();
      state.status = await statusRes.json();
      state.snapshot = await snapshotRes.json();
      state.scores = safeArray((await scoresRes.json()).scores);
      state.alerts = safeArray((await alertsRes.json()).alerts);
      if (!state.signal) state.signal = state.catalog?.default_signal || null;
      ensureSignalSelection();
      renderHeader();
      renderSubsystemChips();
      populateSignalSelect();
      populateSeveritySelect();
      buildWindowButtons();
      renderMetrics();
      renderSnapshot();
      renderQuality();
      renderRiskGrid();
      renderSignalList();
      renderAlerts();
      await loadTrend();
    }

    function attachEvents() {
      document.getElementById("signal-select").addEventListener("change", async (event) => {
        state.signal = event.target.value;
        renderSignalList();
        await loadTrend();
      });
      document.getElementById("severity-select").addEventListener("change", (event) => {
        state.severity = event.target.value;
        renderAlerts();
        renderMetrics();
      });
      document.getElementById("alert-search").addEventListener("input", (event) => {
        state.search = event.target.value.trim();
        renderAlerts();
        renderMetrics();
      });
      document.getElementById("refresh-button").addEventListener("click", async () => {
        await loadBaseData();
      });
    }

    async function refreshLoop() {
      try {
        await loadBaseData();
      } catch (error) {
        document.getElementById("service-status").textContent = "Status: erro ao carregar";
        document.getElementById("alerts-list").innerHTML = `<div class="empty">${String(error)}</div>`;
      }
    }

    attachEvents();
    refreshLoop();
    setInterval(refreshLoop, 30000);
  </script>
</body>
</html>
"""

DASHBOARD_HTML = PART_1 + PART_2 + PART_3 + PART_4
