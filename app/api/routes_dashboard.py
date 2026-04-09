"""Dashboard operacional simples para a API do TA6000."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["dashboard"])


@router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/dashboard", include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>TA6000 Dashboard</title>
  <style>
    :root {
      --bg: #f3efe5;
      --panel: rgba(255, 252, 247, 0.82);
      --panel-strong: #fffaf2;
      --ink: #14213d;
      --muted: #5f6b7a;
      --line: rgba(20, 33, 61, 0.12);
      --ok: #1f7a4d;
      --warn: #cc8b1f;
      --high: #b3472d;
      --critical: #7f1d1d;
      --accent: #0f766e;
      --accent-2: #f59e0b;
      --shadow: 0 18px 48px rgba(20, 33, 61, 0.12);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.18), transparent 32%),
        radial-gradient(circle at top right, rgba(245, 158, 11, 0.18), transparent 24%),
        linear-gradient(180deg, #f7f3ea 0%, #efe7d8 100%);
      min-height: 100vh;
    }

    .shell {
      width: min(1400px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }

    .hero {
      background: linear-gradient(135deg, rgba(20, 33, 61, 0.95), rgba(15, 118, 110, 0.88));
      color: #fff8ed;
      border-radius: 28px;
      padding: 28px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }

    .hero::after {
      content: "";
      position: absolute;
      inset: auto -60px -60px auto;
      width: 220px;
      height: 220px;
      border-radius: 50%;
      background: rgba(245, 158, 11, 0.22);
      filter: blur(8px);
    }

    .hero h1 {
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.6rem);
      letter-spacing: -0.04em;
      line-height: 1;
    }

    .hero p {
      margin: 14px 0 0;
      max-width: 760px;
      color: rgba(255, 248, 237, 0.84);
      font-size: 1.05rem;
    }

    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 248, 237, 0.12);
      border: 1px solid rgba(255, 248, 237, 0.16);
      font-size: 0.92rem;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      margin-top: 20px;
    }

    .card {
      background: var(--panel);
      backdrop-filter: blur(8px);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 20px;
    }

    .stats { grid-column: span 12; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
    .snapshot { grid-column: span 7; }
    .risks { grid-column: span 5; }
    .alerts { grid-column: span 7; }
    .signals { grid-column: span 5; }

    .eyebrow {
      margin: 0 0 10px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 0.76rem;
      font-family: Arial, Helvetica, sans-serif;
    }

    .metric-value {
      font-size: clamp(1.8rem, 3vw, 2.5rem);
      line-height: 1;
      margin: 0 0 6px;
    }

    .metric-note {
      margin: 0;
      color: var(--muted);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.95rem;
    }

    h2 {
      margin: 0 0 16px;
      font-size: 1.55rem;
      letter-spacing: -0.03em;
    }

    .mini-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .mini {
      padding: 14px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
    }

    .mini strong,
    .signal-line strong {
      display: block;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.86rem;
      color: var(--muted);
      margin-bottom: 6px;
      font-weight: 600;
    }

    .mini span,
    .signal-line span {
      font-size: 1.1rem;
    }

    .risk-list,
    .alert-list,
    .signal-list {
      display: grid;
      gap: 12px;
    }

    .risk-item,
    .alert-item,
    .signal-line {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
    }

    .risk-top,
    .alert-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 10px;
    }

    .risk-name,
    .alert-title {
      font-size: 1rem;
      font-weight: 700;
      font-family: Arial, Helvetica, sans-serif;
    }

    .risk-bar {
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: rgba(20, 33, 61, 0.08);
      overflow: hidden;
      margin: 10px 0 8px;
    }

    .risk-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--ok), var(--accent-2), var(--high));
    }

    .pill {
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .sev-low { background: rgba(31, 122, 77, 0.12); color: var(--ok); }
    .sev-medium { background: rgba(204, 139, 31, 0.15); color: var(--warn); }
    .sev-high { background: rgba(179, 71, 45, 0.14); color: var(--high); }
    .sev-critical { background: rgba(127, 29, 29, 0.14); color: var(--critical); }

    .subtext,
    .alert-meta,
    .timestamp {
      color: var(--muted);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 0.88rem;
      line-height: 1.45;
    }

    .empty {
      padding: 20px;
      border: 1px dashed var(--line);
      border-radius: 16px;
      color: var(--muted);
      font-family: Arial, Helvetica, sans-serif;
      background: rgba(255, 255, 255, 0.45);
    }

    @media (max-width: 1100px) {
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .snapshot, .risks, .alerts, .signals { grid-column: span 12; }
    }

    @media (max-width: 720px) {
      .shell { width: min(100vw - 20px, 1400px); }
      .hero { padding: 22px; border-radius: 20px; }
      .stats, .mini-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>TA6000 Operational View</h1>
      <p>Painel de leitura operacional para monitoramento do compressor, com risco por subsistema, alertas ativos e snapshot mais recente.</p>
      <div class="badges">
        <div class="badge" id="service-status">Status: carregando...</div>
        <div class="badge" id="data-source">Fonte: ...</div>
        <div class="badge" id="last-refresh">Atualizacao: ...</div>
      </div>
    </section>

    <section class="grid">
      <div class="stats">
        <article class="card">
          <p class="eyebrow">Alertas ativos</p>
          <h2 class="metric-value" id="metric-alerts">--</h2>
          <p class="metric-note">Total de alertas ativos no ciclo atual</p>
        </article>
        <article class="card">
          <p class="eyebrow">Maior risco</p>
          <h2 class="metric-value" id="metric-highest-risk">--</h2>
          <p class="metric-note" id="metric-highest-risk-label">Aguardando leitura</p>
        </article>
        <article class="card">
          <p class="eyebrow">Modo operacional</p>
          <h2 class="metric-value" id="metric-mode">--</h2>
          <p class="metric-note">Estado atual do compressor</p>
        </article>
        <article class="card">
          <p class="eyebrow">Timestamp</p>
          <h2 class="metric-value" id="metric-timestamp">--</h2>
          <p class="metric-note">Ultima amostra disponivel</p>
        </article>
      </div>

      <section class="card snapshot">
        <h2>Snapshot Atual</h2>
        <div class="mini-grid" id="snapshot-grid"></div>
      </section>

      <section class="card risks">
        <h2>Risco por Subsistema</h2>
        <div class="risk-list" id="risk-list"></div>
      </section>

      <section class="card alerts">
        <h2>Alertas Ativos</h2>
        <div class="alert-list" id="alert-list"></div>
      </section>

      <section class="card signals">
        <h2>Indicadores-Chave</h2>
        <div class="signal-list" id="signal-list"></div>
      </section>
    </section>
  </main>

  <script>
    const keySignals = [
      ["pv_pres_sistema_bar", "Pressao do sistema (bar)"],
      ["pv_pres_descarga_bar", "Pressao de descarga (bar)"],
      ["pv_temp_oleo_lubrificacao_c", "Temperatura do oleo (C)"],
      ["pv_corr_motor_a", "Corrente do motor (A)"],
      ["pv_vib_estagio_1_mils", "Vibracao 1o estagio (mils)"],
      ["pv_vib_estagio_2_mils", "Vibracao 2o estagio (mils)"],
      ["pv_vib_estagio_3_mils", "Vibracao 3o estagio (mils)"],
      ["pv_pres_vacuo_cx_engran_inh2o", "Vacuo cx engrenagem (inH2O)"]
    ];

    function formatValue(value) {
      if (value === null || value === undefined || value === "") return "--";
      if (typeof value === "number") return value.toFixed(2);
      return String(value);
    }

    function formatDate(value) {
      if (!value) return "--";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString("pt-BR");
    }

    function severityClass(severity) {
      return `sev-${String(severity || "low").toLowerCase()}`;
    }

    function renderSnapshot(snapshot) {
      const values = snapshot?.values || {};
      const grid = document.getElementById("snapshot-grid");
      const pairs = [
        ["st_oper", "Estado operacional"],
        ["st_carga_oper", "Estado de carga"],
        ["ds_turno", "Turno"],
        ["status", "Status"],
        ["st_plc", "PLC"],
        ["is_normal_operation", "Operacao normal"],
        ["mode_key", "Chave de modo"],
        ["timestamp", "Timestamp"]
      ];

      grid.innerHTML = pairs.map(([key, label]) => `
        <div class="mini">
          <strong>${label}</strong>
          <span>${formatValue(values[key] ?? snapshot?.[key])}</span>
        </div>
      `).join("");
    }

    function renderSignals(snapshot) {
      const values = snapshot?.values || {};
      const container = document.getElementById("signal-list");
      container.innerHTML = keySignals.map(([key, label]) => `
        <div class="signal-line">
          <strong>${label}</strong>
          <span>${formatValue(values[key])}</span>
        </div>
      `).join("");
    }

    function renderRisks(scores) {
      const container = document.getElementById("risk-list");
      if (!scores?.length) {
        container.innerHTML = '<div class="empty">Sem score disponivel no momento.</div>';
        return;
      }

      container.innerHTML = scores.map((item) => `
        <div class="risk-item">
          <div class="risk-top">
            <div class="risk-name">${item.subsystem}</div>
            <span class="pill ${severityClass(item.highest_severity || "low")}">${item.score}</span>
          </div>
          <div class="risk-bar"><div class="risk-fill" style="width:${Math.min(100, item.score)}%"></div></div>
          <div class="subtext">Alertas ativos: ${item.active_alerts}</div>
          <div class="subtext">${(item.rationale || []).join(" | ") || "Sem alertas relevantes."}</div>
        </div>
      `).join("");
    }

    function renderAlerts(alerts) {
      const container = document.getElementById("alert-list");
      if (!alerts?.length) {
        container.innerHTML = '<div class="empty">Nenhum alerta ativo.</div>';
        return;
      }

      container.innerHTML = alerts.map((alert) => `
        <div class="alert-item">
          <div class="alert-top">
            <div class="alert-title">${alert.title}</div>
            <span class="pill ${severityClass(alert.severity)}">${alert.severity}</span>
          </div>
          <div class="subtext">${alert.message}</div>
          <div class="alert-meta">Subsistema: ${alert.subsystem} | Sinal: ${alert.signal || "--"} | Valor: ${formatValue(alert.current_value)} | Regra: ${alert.rule_id}</div>
          <div class="timestamp">Ultima ocorrencia: ${formatDate(alert.last_seen_at)}</div>
        </div>
      `).join("");
    }

    async function loadDashboard() {
      try {
        const [statusRes, snapshotRes, scoresRes, alertsRes] = await Promise.all([
          fetch("/status"),
          fetch("/status/current"),
          fetch("/status/scores"),
          fetch("/alerts")
        ]);

        const [status, snapshot, scores, alerts] = await Promise.all([
          statusRes.json(),
          snapshotRes.json(),
          scoresRes.json(),
          alertsRes.json()
        ]);

        document.getElementById("service-status").textContent = `Status: ${status.service_status || "--"}`;
        document.getElementById("data-source").textContent = `Fonte: ${status.data_source || "--"}`;
        document.getElementById("last-refresh").textContent = `Atualizacao: ${formatDate(status.last_refresh_at)}`;

        document.getElementById("metric-alerts").textContent = String(alerts.count ?? 0);
        const topScore = (scores.scores || [])[0];
        document.getElementById("metric-highest-risk").textContent = topScore ? formatValue(topScore.score) : "--";
        document.getElementById("metric-highest-risk-label").textContent = topScore ? topScore.subsystem : "Sem score";
        document.getElementById("metric-mode").textContent = snapshot.mode_key || "--";
        document.getElementById("metric-timestamp").textContent = snapshot.timestamp ? formatDate(snapshot.timestamp) : "--";

        renderSnapshot(snapshot);
        renderSignals(snapshot);
        renderRisks(scores.scores || []);
        renderAlerts(alerts.alerts || []);
      } catch (error) {
        document.getElementById("service-status").textContent = "Status: erro ao carregar";
        document.getElementById("alert-list").innerHTML = `<div class="empty">${String(error)}</div>`;
      }
    }

    loadDashboard();
    setInterval(loadDashboard, 30000);
  </script>
</body>
</html>
        """
    )
