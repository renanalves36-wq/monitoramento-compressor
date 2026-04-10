const SUBSYSTEM_LABELS = {
  all: "Visao geral",
  ar_processo: "Ar / Processo",
  lubrificacao: "Lubrificacao",
  vibracao: "Vibracao",
  motor: "Motor",
  operacao: "Operacao",
};

const SEVERITY_LABELS = {
  all: "todas",
  low: "baixa",
  medium: "media",
  high: "alta",
  critical: "critica",
};

const QUICK_PRESETS = [
  { label: "90 min", value: 90, unit: "minutes", bucket: "minutes" },
  { label: "6 h", value: 6, unit: "hours", bucket: "minutes" },
  { label: "12 h", value: 12, unit: "hours", bucket: "minutes" },
  { label: "24 h", value: 24, unit: "hours", bucket: "hours" },
  { label: "3 dias", value: 3, unit: "days", bucket: "hours" },
  { label: "7 dias", value: 7, unit: "days", bucket: "hours" },
  { label: "30 dias", value: 30, unit: "days", bucket: "days" },
];

const OVERVIEW_SIGNALS = [
  "pv_pres_sistema_bar",
  "pv_temp_oleo_lubrificacao_c",
  "pv_vib_max_mils",
  "pv_corr_motor_a",
];

const state = {
  catalog: null,
  status: null,
  snapshot: null,
  scores: [],
  activeAlerts: [],
  recentAlerts: [],
  trend: null,
  subsystem: "all",
  severity: "all",
  signal: null,
  rangeValue: 24,
  rangeUnit: "hours",
  bucket: "hours",
  search: "",
  trendRequestId: 0,
};

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${url}: HTTP ${response.status}`);
  }
  return response.json();
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function friendlySubsystem(value) {
  return SUBSYSTEM_LABELS[value] || String(value || "--");
}

function severityClass(severity) {
  return `severity-${String(severity || "all").toLowerCase()}`;
}

function severityLabel(severity) {
  return SEVERITY_LABELS[String(severity || "all").toLowerCase()] || String(severity || "--");
}

function severityWeight(severity) {
  const table = { low: 1, medium: 2, high: 3, critical: 4 };
  return table[String(severity || "").toLowerCase()] || 0;
}

function scoreColor(score) {
  if (score >= 80) return "#f26969";
  if (score >= 60) return "#ef9a58";
  if (score >= 35) return "#f0c85d";
  return "#8ecf87";
}

function formatNumber(value, digits = null) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  const decimals = digits === null ? (Math.abs(numeric) >= 100 ? 0 : 2) : digits;
  return numeric.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatMaybe(value, unit = "", digits = null) {
  if (value === null || value === undefined || value === "") return "--";
  return `${formatNumber(value, digits)}${unit ? ` ${unit}` : ""}`;
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("pt-BR");
}

function formatAxisDate(value, rangeUnit = state.rangeUnit, bucket = state.trend?.bucket || state.bucket) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const showDate = rangeUnit === "days" || bucket === "days";
  const showOnlyTime = rangeUnit === "minutes" && bucket !== "days";
  if (showDate) {
    return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  }
  if (showOnlyTime) {
    return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getSignalMeta(signal) {
  return safeArray(state.catalog?.signals).find((item) => item.signal === signal) || null;
}

function getTargetLabel(signalMeta, fallback = "Setpoint") {
  if (!signalMeta) return fallback;
  return signalMeta.default_target_label || fallback;
}

function getTargetValue(signalMeta, values = {}, fallback = null) {
  if (!signalMeta) return fallback;
  if (signalMeta.default_target_signal) {
    const currentTarget = values?.[signalMeta.default_target_signal];
    if (currentTarget !== null && currentTarget !== undefined && currentTarget !== "") {
      return currentTarget;
    }
  }
  if (signalMeta.target_value !== null && signalMeta.target_value !== undefined) {
    return signalMeta.target_value;
  }
  return fallback;
}

function formatOperatingRange(lowerLimit, upperLimit, unit = "") {
  const lowerText = formatMaybe(lowerLimit, unit);
  const upperText = formatMaybe(upperLimit, unit);
  if ((lowerLimit === null || lowerLimit === undefined) && (upperLimit === null || upperLimit === undefined)) {
    return "sem faixa configurada";
  }
  if (lowerLimit !== null && lowerLimit !== undefined && upperLimit !== null && upperLimit !== undefined) {
    return `${lowerText} ate ${upperText}`;
  }
  if (lowerLimit !== null && lowerLimit !== undefined) {
    return `a partir de ${lowerText}`;
  }
  return `ate ${upperText}`;
}

function getVisibleSignals() {
  const signals = safeArray(state.catalog?.signals);
  const filtered = state.subsystem === "all"
    ? signals
    : signals.filter((item) => item.subsystem === state.subsystem);

  return filtered
    .filter((item) => {
      if (!state.search) return true;
      const haystack = `${item.label} ${item.signal} ${friendlySubsystem(item.subsystem)}`.toLowerCase();
      return haystack.includes(state.search.toLowerCase());
    })
    .sort((left, right) => {
      if (right.active_alerts !== left.active_alerts) return right.active_alerts - left.active_alerts;
      return left.label.localeCompare(right.label, "pt-BR");
    });
}

function countAlertsForSignal(signal, alerts) {
  return alerts.filter((alert) => alert.signal === signal).length;
}

function getPreferredSignals() {
  const visible = getVisibleSignals();
  if (state.subsystem === "all") {
    const overview = OVERVIEW_SIGNALS
      .map((signal) => visible.find((item) => item.signal === signal))
      .filter(Boolean);
    if (overview.length) return overview.slice(0, 4);
  }
  return visible.slice(0, 4);
}

function ensureSignalSelection() {
  const visible = getVisibleSignals();
  if (!visible.length) {
    state.signal = null;
    return;
  }
  if (visible.some((item) => item.signal === state.signal)) return;
  const withActive = visible.find((item) => item.active_alerts > 0);
  state.signal = (withActive || visible[0]).signal;
}

function alertMatchesFilters(alert) {
  const matchesSubsystem = state.subsystem === "all" || alert.subsystem === state.subsystem;
  const matchesSeverity = state.severity === "all" || alert.severity === state.severity;
  const haystack = `${alert.title} ${alert.message} ${alert.rule_id} ${alert.subsystem} ${alert.signal || ""}`.toLowerCase();
  const matchesSearch = !state.search || haystack.includes(state.search.toLowerCase());
  return matchesSubsystem && matchesSeverity && matchesSearch;
}

function getFilteredActiveAlerts() {
  return safeArray(state.activeAlerts)
    .filter((alert) => alertMatchesFilters(alert))
    .sort((left, right) => {
      const severityDelta = severityWeight(right.severity) - severityWeight(left.severity);
      if (severityDelta !== 0) return severityDelta;
      return new Date(right.last_seen_at) - new Date(left.last_seen_at);
    });
}

function getFilteredRecentAlerts() {
  return safeArray(state.recentAlerts)
    .filter((alert) => !alert.is_active)
    .filter((alert) => alertMatchesFilters(alert))
    .sort((left, right) => new Date(right.last_seen_at) - new Date(left.last_seen_at));
}

function getSelectedSignalAlerts() {
  const alerts = safeArray(state.recentAlerts).filter(
    (alert) => alert.signal === state.signal && alertMatchesFilters(alert)
  );
  return alerts.sort((left, right) => new Date(right.last_seen_at) - new Date(left.last_seen_at));
}

function syncFilterInputs() {
  document.getElementById("severity-select").value = state.severity;
  document.getElementById("range-value").value = String(state.rangeValue);
  document.getElementById("range-unit").value = state.rangeUnit;
  document.getElementById("bucket-select").value = state.bucket;
  const signalSelect = document.getElementById("signal-select");
  if (state.signal) signalSelect.value = state.signal;
}

function setTrendLoading() {
  document.getElementById("trend-title").textContent = "Atualizando grafico...";
  document.getElementById("trend-subtitle").textContent = "Buscando nova serie temporal para o indicador selecionado.";
  document.getElementById("trend-chart").innerHTML = "";
  document.getElementById("chart-tooltip").classList.remove("visible");
}

async function focusSignal(signal, subsystem = null) {
  if (subsystem) {
    state.subsystem = subsystem;
  }
  state.signal = signal;
  ensureSignalSelection();
  renderAll();
  setTrendLoading();
  await loadTrend();
}

function renderSubsystemPills() {
  const container = document.getElementById("subsystem-pills");
  const subsystems = ["all", ...safeArray(state.catalog?.subsystems)];
  container.innerHTML = subsystems
    .map((subsystem) => `
      <button class="pill-button ${state.subsystem === subsystem ? "active" : ""}" data-subsystem="${subsystem}" type="button">
        ${friendlySubsystem(subsystem)}
      </button>
    `)
    .join("");

  container.querySelectorAll("[data-subsystem]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.subsystem = button.dataset.subsystem;
      ensureSignalSelection();
      renderAll();
      setTrendLoading();
      await loadTrend();
    });
  });
}

function renderPresetButtons() {
  const container = document.getElementById("preset-row");
  container.innerHTML = QUICK_PRESETS.map((preset) => {
    const isActive = preset.value === state.rangeValue && preset.unit === state.rangeUnit && preset.bucket === state.bucket;
    return `
      <button class="pill-button ${isActive ? "active" : ""}" data-range-value="${preset.value}" data-range-unit="${preset.unit}" data-bucket="${preset.bucket}" type="button">
        ${preset.label}
      </button>
    `;
  }).join("");

  container.querySelectorAll("[data-range-value]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.rangeValue = Number(button.dataset.rangeValue);
      state.rangeUnit = button.dataset.rangeUnit;
      state.bucket = button.dataset.bucket;
      syncFilterInputs();
      renderPresetButtons();
      setTrendLoading();
      await loadTrend();
    });
  });
}

function populateSelects() {
  const signalSelect = document.getElementById("signal-select");
  const visibleSignals = getVisibleSignals();
  signalSelect.innerHTML = visibleSignals.map((item) => `
    <option value="${item.signal}">${item.label} (${friendlySubsystem(item.subsystem)})</option>
  `).join("");

  const severitySelect = document.getElementById("severity-select");
  severitySelect.innerHTML = safeArray(state.catalog?.severities)
    .map((severity) => `<option value="${severity}">${severityLabel(severity)}</option>`)
    .join("");

  syncFilterInputs();
}

function renderTopbar() {
  const snapshot = state.snapshot || {};
  const status = state.status || {};
  const modeLabel = [snapshot.st_oper, snapshot.st_carga_oper].filter(Boolean).join(" - ") || "Sem modo identificado";
  document.getElementById("hero-status").textContent = modeLabel;
  document.getElementById("hero-description").textContent =
    `Base carregada com ${formatNumber(status.history_rows, 0)} leituras entre ${formatDateTime(status.earliest_timestamp)} e ${formatDateTime(status.latest_timestamp)}. ` +
    `${formatNumber(status.active_alerts, 0)} alertas ativos agora e ${formatNumber(status.recent_alert_events, 0)} eventos detectados na base analisada.`;
  document.getElementById("badge-source").textContent = `Fonte: ${status.data_source || "--"}`;
  document.getElementById("badge-refresh").textContent = `Atualizacao: ${formatDateTime(status.last_refresh_at)}`;
  document.getElementById("badge-range").textContent = `Cobertura: ${formatDateTime(status.earliest_timestamp)} ate ${formatDateTime(status.latest_timestamp)}`;
  document.getElementById("badge-rows").textContent = `Leituras: ${formatNumber(status.history_rows, 0)}`;
}

function renderOperationalPanel() {
  const snapshot = state.snapshot || {};
  const values = snapshot.values || {};
  document.getElementById("snapshot-ts").textContent = `Ultima leitura: ${formatDateTime(snapshot.timestamp)}`;

  const stripItems = [
    ["Estado operacional", snapshot.st_oper || "--", "state-ok"],
    ["Estado de carga", snapshot.st_carga_oper || "--", "state-ok"],
    ["Modo observado", snapshot.mode_key || "--", "severity-all"],
  ];
  document.getElementById("status-strip").innerHTML = stripItems.map(([label, value, styleClass]) => `
    <div class="status-chip">
      <strong>${label}</strong>
      <span>${value}</span>
      <div class="stack-footer"><span class="severity-pill ${styleClass}">${label === "Modo observado" ? "contexto" : "ok"}</span></div>
    </div>
  `).join("");

  const heroSignals = getPreferredSignals();
  const activeAlerts = getFilteredActiveAlerts();
  document.getElementById("hero-kpis").innerHTML = heroSignals.length
    ? heroSignals.map((item) => {
        const activeCount = countAlertsForSignal(item.signal, activeAlerts);
        const unit = item.unit || "";
        const targetValue = getTargetValue(item, values);
        const targetLabel = getTargetLabel(item);
        return `
          <div class="kpi-card ${activeCount ? "highlight" : ""}">
            <div class="stack-top">
              <div>
                <strong>${item.label}</strong>
                <div class="kpi-value">${formatMaybe(values[item.signal], unit)}</div>
              </div>
              <span class="severity-pill ${activeCount ? "severity-high" : "severity-all"}">${activeCount} ativos</span>
            </div>
            <div class="stack-meta">${targetLabel}: ${formatMaybe(targetValue, unit)}</div>
            <div class="stack-meta">Faixa operacional: ${formatOperatingRange(item.lower_limit, item.upper_limit, unit)}</div>
          </div>
        `;
      }).join("")
    : '<div class="empty-state">Nao ha sinais disponiveis para o subsistema escolhido.</div>';
}

function renderScorePanel() {
  const container = document.getElementById("score-grid");
  container.innerHTML = safeArray(state.scores).map((item) => `
    <div class="score-card ${state.subsystem === item.subsystem ? "active" : ""}" data-score-subsystem="${item.subsystem}">
      <div class="score-top">
        <div class="gauge" style="--value:${Math.min(100, item.score)}; --gauge-color:${scoreColor(item.score)};">
          <div class="gauge-value">
            <strong>${formatNumber(item.score, 0)}</strong>
            <small>nota</small>
          </div>
        </div>
        <div>
          <div class="signal-title">${friendlySubsystem(item.subsystem)}</div>
          <div class="signal-meta">${item.rationale?.[0] || "Sem sinal de destaque agora."}</div>
          <div class="score-caption">${item.active_alerts} alertas ativos | maior severidade: ${severityLabel(item.highest_severity || "all")}</div>
        </div>
      </div>
      <div class="score-bar"><div class="score-fill" style="width:${Math.min(100, item.score)}%"></div></div>
    </div>
  `).join("");

  container.querySelectorAll("[data-score-subsystem]").forEach((element) => {
    element.addEventListener("click", async () => {
      state.subsystem = element.dataset.scoreSubsystem;
      ensureSignalSelection();
      renderAll();
      setTrendLoading();
      await loadTrend();
    });
  });
}

function renderContextPanel() {
  const snapshot = state.snapshot || {};
  const values = snapshot.values || {};
  const trend = state.trend || {};
  const signalMeta = getSignalMeta(state.signal);
  const unit = signalMeta?.unit || trend.unit || "";
  const targetLabel = trend.target_label || getTargetLabel(signalMeta);
  const targetValue = trend.summary?.target_current ?? getTargetValue(signalMeta, values, trend.target_value);

  const cards = [
    ["Indicador principal", signalMeta?.label || "--"],
    ["Valor atual", formatMaybe(trend.summary?.latest, unit)],
    [targetLabel, formatMaybe(targetValue, unit)],
    ["Limite inferior", formatMaybe(trend.lower_limit, unit)],
    ["Limite superior", formatMaybe(trend.upper_limit, unit)],
    ["Turno", values.ds_turno || "--"],
    ["PLC", String(values.st_plc ?? "--")],
  ];
  document.getElementById("context-grid").innerHTML = cards.map(([label, value]) => `
    <div class="context-card">
      <strong>${label}</strong>
      <div class="context-value">${value}</div>
    </div>
  `).join("");

  const rules = safeArray(trend.rules);
  document.getElementById("rule-list").innerHTML = rules.length
    ? rules.map((rule) => `
        <div class="stack-item">
          <div class="stack-top">
            <div>
              <div class="stack-title-main">${rule.title}</div>
              <div class="stack-meta">${rule.rule_id} | ${rule.layer}</div>
            </div>
            <span class="severity-pill ${severityClass(rule.severity)}">${severityLabel(rule.severity)}</span>
          </div>
          <div class="stack-footer">${rule.condition || "--"} ${rule.threshold || ""}</div>
        </div>
      `).join("")
    : '<div class="empty-state">Nao ha regras associadas ao indicador atual.</div>';
}

function renderQualityPanel() {
  const snapshot = state.snapshot || {};
  const issues = safeArray(snapshot.data_quality_issues);
  document.getElementById("quality-list").innerHTML = issues.length
    ? issues.map((issue) => `
        <div class="stack-item">
          <div class="stack-title-main">${issue.issue_type}</div>
          <div class="stack-meta">${issue.signal || "geral"} | ${issue.message}</div>
        </div>
      `).join("")
    : '<div class="empty-state">Nenhuma observacao de qualidade foi apontada na ultima amostra.</div>';
}

function renderAlertList(containerId, alerts, emptyText, counterId) {
  const container = document.getElementById(containerId);
  document.getElementById(counterId).textContent = `${formatNumber(alerts.length, 0)} ${containerId === "active-alert-list" ? "alertas" : "eventos"}`;
  container.innerHTML = alerts.length
    ? alerts.map((alert) => `
        <div class="stack-item clickable" data-alert-signal="${alert.signal || ""}" data-alert-subsystem="${alert.subsystem}">
          <div class="stack-top">
            <div>
              <div class="stack-title-main">${alert.title}</div>
              <div class="stack-meta">${friendlySubsystem(alert.subsystem)} | ${alert.signal || "--"} | ${alert.rule_id}</div>
            </div>
            <span class="severity-pill ${severityClass(alert.severity)}">${severityLabel(alert.severity)}</span>
          </div>
          <div class="stack-meta">${alert.message}</div>
          <div class="stack-footer">
            Valor: ${formatMaybe(alert.current_value)} | Ultima ocorrencia: ${formatDateTime(alert.last_seen_at)}
          </div>
        </div>
      `).join("")
    : `<div class="empty-state">${emptyText}</div>`;

  container.querySelectorAll("[data-alert-signal]").forEach((element) => {
    element.addEventListener("click", async () => {
      const nextSignal = element.dataset.alertSignal;
      const nextSubsystem = element.dataset.alertSubsystem;
      if (!nextSignal) return;
      await focusSignal(nextSignal, nextSubsystem || null);
    });
  });
}

function renderAlertPanels() {
  renderAlertList(
    "recent-alert-list",
    getFilteredRecentAlerts().slice(0, 80),
    "Nenhum evento historico encontrado dentro dos filtros escolhidos.",
    "recent-count",
  );
  renderAlertList(
    "active-alert-list",
    getFilteredActiveAlerts().slice(0, 80),
    "Nenhum alerta ativo para os filtros atuais.",
    "active-count",
  );
}

function renderSignalExplorer() {
  const container = document.getElementById("signal-list");
  const visibleSignals = getVisibleSignals();
  document.getElementById("signal-panel-note").textContent =
    `${friendlySubsystem(state.subsystem)} | ${formatNumber(visibleSignals.length, 0)} sinais visiveis`;

  container.innerHTML = visibleSignals.length
    ? visibleSignals.map((item) => {
        const values = state.snapshot?.values || {};
        const activeCount = countAlertsForSignal(item.signal, safeArray(state.activeAlerts));
        const recentCount = countAlertsForSignal(item.signal, safeArray(state.recentAlerts));
        const targetValue = getTargetValue(item, values);
        const targetLabel = getTargetLabel(item);
        return `
          <div class="signal-item ${state.signal === item.signal ? "active" : ""}" data-signal="${item.signal}">
            <div class="signal-top">
              <div>
                <div class="signal-title">${item.label}</div>
                <div class="signal-subvalue">${formatMaybe(values[item.signal], item.unit || "")}</div>
              </div>
              <span class="severity-pill ${activeCount ? "severity-high" : recentCount ? "severity-medium" : "severity-all"}">
                ${activeCount ? `${activeCount} ativos` : `${recentCount} eventos`}
              </span>
            </div>
            <div class="signal-meta">${friendlySubsystem(item.subsystem)} | ${item.signal}</div>
            <div class="signal-footer">
              ${targetLabel}: ${formatMaybe(targetValue, item.unit || "")} | Faixa: ${formatOperatingRange(item.lower_limit, item.upper_limit, item.unit || "")}
            </div>
          </div>
        `;
      }).join("")
    : '<div class="empty-state">Nenhum sinal corresponde aos filtros atuais.</div>';

  container.querySelectorAll("[data-signal]").forEach((element) => {
    element.addEventListener("click", async () => {
      await focusSignal(element.dataset.signal);
    });
  });
}

function renderTrendSummary() {
  const trend = state.trend || {};
  const summary = trend.summary || {};
  const unit = trend.unit || "";
  const targetLabel = trend.target_label || "Setpoint";
  const cards = [
    ["Valor atual", formatMaybe(summary.latest, unit)],
    [targetLabel, formatMaybe(summary.target_current ?? trend.target_value, unit)],
    ["Limite inferior", formatMaybe(trend.lower_limit, unit)],
    ["Limite superior", formatMaybe(trend.upper_limit, unit)],
    ["Tendencia 15 min", formatMaybe(summary.slope_15m, unit ? `${unit}/min` : "")],
    ["Z-score 1h", formatMaybe(summary.zscore_1h)],
  ];
  document.getElementById("trend-summary-grid").innerHTML = cards.map(([label, value]) => `
    <div class="context-card">
      <strong>${label}</strong>
      <div class="context-value">${value}</div>
    </div>
  `).join("");
}

function buildPath(points, xKey, yKey) {
  const filtered = points.filter((point) => point[yKey] !== null && point[yKey] !== undefined);
  if (!filtered.length) return "";
  return filtered.map((point, index) => `${index === 0 ? "M" : "L"} ${point[xKey]} ${point[yKey]}`).join(" ");
}

function getMarkerColor(severity) {
  const map = {
    low: "#8ecf87",
    medium: "#f0c85d",
    high: "#ef9a58",
    critical: "#f26969",
  };
  return map[String(severity || "").toLowerCase()] || "#f0c85d";
}

function renderChart() {
  const svg = document.getElementById("trend-chart");
  const tooltip = document.getElementById("chart-tooltip");
  const trend = state.trend || {};
  const points = safeArray(trend.points);
  const title = document.getElementById("trend-title");
  const subtitle = document.getElementById("trend-subtitle");

  if (!points.length) {
    title.textContent = "Sem dados suficientes para o indicador atual";
    subtitle.textContent = "A serie temporal ficou vazia para a janela escolhida.";
    svg.innerHTML = "";
    tooltip.classList.remove("visible");
    return;
  }

  const unit = trend.unit || "";
  title.textContent = `${trend.label} (${trend.signal})`;
  subtitle.textContent = `${friendlySubsystem(trend.subsystem)} | ${points.length} pontos | janela: ${trend.range_value} ${trend.range_unit} | agrupamento: ${trend.bucket}`;

  const width = 960;
  const height = 430;
  const margin = { top: 26, right: 26, bottom: 48, left: 78 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const timestamps = points.map((point) => new Date(point.timestamp).getTime()).filter(Number.isFinite);
  if (!timestamps.length) {
    title.textContent = `${trend.label} (${trend.signal})`;
    subtitle.textContent = "Nao foi possivel interpretar os timestamps retornados para a serie temporal.";
    svg.innerHTML = "";
    tooltip.classList.remove("visible");
    return;
  }
  const minTs = Math.min(...timestamps);
  const maxTs = Math.max(...timestamps);
  const xScale = (value) => {
    if (maxTs === minTs) return margin.left + plotWidth / 2;
    return margin.left + ((value - minTs) / (maxTs - minTs)) * plotWidth;
  };

  const numericValues = [];
  points.forEach((point) => {
    [point.value, point.target_value, point.rolling_mean, point.ewma, point.lower_limit, point.upper_limit].forEach((candidate) => {
      const numeric = Number(candidate);
      if (Number.isFinite(numeric)) numericValues.push(numeric);
    });
  });
  if (!numericValues.length) {
    title.textContent = `${trend.label} (${trend.signal})`;
    subtitle.textContent = "A janela atual nao trouxe valores numericos suficientes para desenhar o grafico.";
    svg.innerHTML = "";
    tooltip.classList.remove("visible");
    return;
  }

  const rawMin = Math.min(...numericValues);
  const rawMax = Math.max(...numericValues);
  const padding = rawMin === rawMax ? Math.max(Math.abs(rawMax), 1) * 0.12 : (rawMax - rawMin) * 0.12;
  const minValue = rawMin - padding;
  const maxValue = rawMax + padding;
  const yScale = (value) => {
    if (maxValue === minValue) return margin.top + plotHeight / 2;
    const normalized = (value - minValue) / (maxValue - minValue);
    return margin.top + plotHeight - normalized * plotHeight;
  };

  const chartPoints = points.map((point) => ({
    ...point,
    rawTs: new Date(point.timestamp).getTime(),
    x: xScale(new Date(point.timestamp).getTime()),
    y: point.value === null || point.value === undefined ? null : yScale(Number(point.value)),
    meanY: point.rolling_mean === null || point.rolling_mean === undefined ? null : yScale(Number(point.rolling_mean)),
    ewmaY: point.ewma === null || point.ewma === undefined ? null : yScale(Number(point.ewma)),
    targetY: point.target_value === null || point.target_value === undefined ? null : yScale(Number(point.target_value)),
    lowerY: point.lower_limit === null || point.lower_limit === undefined ? null : yScale(Number(point.lower_limit)),
    upperY: point.upper_limit === null || point.upper_limit === undefined ? null : yScale(Number(point.upper_limit)),
  }));

  const gridLines = [];
  for (let step = 0; step <= 4; step += 1) {
    const y = margin.top + (plotHeight / 4) * step;
    const value = maxValue - ((maxValue - minValue) / 4) * step;
    gridLines.push(`
      <line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="5 7" />
      <text x="${margin.left - 12}" y="${y + 4}" fill="rgba(168,173,184,0.95)" font-size="12" text-anchor="end" font-family="Arial, Helvetica, sans-serif">${formatNumber(value)}</text>
    `);
  }

  const xTicks = [];
  for (let index = 0; index < 5; index += 1) {
    const ts = minTs + ((maxTs - minTs) / 4) * index;
    const x = xScale(ts);
    xTicks.push(`
      <text x="${x}" y="${height - 14}" fill="rgba(168,173,184,0.95)" font-size="12" text-anchor="middle" font-family="Arial, Helvetica, sans-serif">${formatAxisDate(ts, trend.range_unit, trend.bucket)}</text>
    `);
  }

  let bandMarkup = "";
  const lastPoint = chartPoints[chartPoints.length - 1];
  const highlightY =
    lastPoint.y ??
    lastPoint.targetY ??
    lastPoint.meanY ??
    lastPoint.ewmaY ??
    (margin.top + plotHeight / 2);
  if (lastPoint.lower_limit !== null && lastPoint.lower_limit !== undefined && lastPoint.upper_limit !== null && lastPoint.upper_limit !== undefined) {
    const bandTop = yScale(Number(lastPoint.upper_limit));
    const bandBottom = yScale(Number(lastPoint.lower_limit));
    bandMarkup = `<rect x="${margin.left}" y="${bandTop}" width="${plotWidth}" height="${bandBottom - bandTop}" fill="rgba(35,163,156,0.09)" rx="16" />`;
  }

  const actualPath = buildPath(chartPoints, "x", "y");
  const meanPath = buildPath(chartPoints, "x", "meanY");
  const ewmaPath = buildPath(chartPoints, "x", "ewmaY");
  const targetPath = buildPath(chartPoints, "x", "targetY");
  const lowerPath = buildPath(chartPoints, "x", "lowerY");
  const upperPath = buildPath(chartPoints, "x", "upperY");

  const markerAlerts = getSelectedSignalAlerts().filter((alert) => {
    const ts = new Date(alert.last_seen_at).getTime();
    return Number.isFinite(ts) && ts >= minTs && ts <= maxTs;
  }).slice(0, 80);

  const markerMarkup = markerAlerts.map((alert) => {
    const ts = new Date(alert.last_seen_at).getTime();
    const x = xScale(ts);
    const nearestPoint = chartPoints.reduce((best, point) => {
      if (!best) return point;
      return Math.abs(point.rawTs - ts) < Math.abs(best.rawTs - ts) ? point : best;
    }, null);
    const y = nearestPoint?.y ?? margin.top + 16;
    const color = getMarkerColor(alert.severity);
    return `
      <line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" stroke="${color}" stroke-opacity="0.25" stroke-dasharray="4 8" />
      <circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="#121212" stroke-width="2" />
    `;
  }).join("");

  svg.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" />
    ${bandMarkup}
    ${gridLines.join("")}
    <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(255,255,255,0.12)" />
    ${markerMarkup}
    <path d="${targetPath}" fill="none" stroke="#f0c85d" stroke-width="2.2" stroke-dasharray="9 7" stroke-linecap="round" />
    <path d="${upperPath}" fill="none" stroke="#f2a35d" stroke-width="1.9" stroke-dasharray="4 6" stroke-linecap="round" />
    <path d="${lowerPath}" fill="none" stroke="#8ecf87" stroke-width="1.9" stroke-dasharray="4 6" stroke-linecap="round" />
    <path d="${meanPath}" fill="none" stroke="#153150" stroke-width="2.5" stroke-linecap="round" />
    <path d="${ewmaPath}" fill="none" stroke="#c26e23" stroke-width="2.3" stroke-dasharray="6 6" stroke-linecap="round" />
    <path d="${actualPath}" fill="none" stroke="#23a39c" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="${lastPoint.x}" cy="${highlightY}" r="6" fill="#23a39c" />
    ${xTicks.join("")}
  `;

  svg.onmouseleave = () => tooltip.classList.remove("visible");
  svg.onmousemove = (event) => {
    const bounds = svg.getBoundingClientRect();
    const relativeX = ((event.clientX - bounds.left) / bounds.width) * width;
    const nearest = chartPoints.reduce((best, point) => {
      if (!best) return point;
      return Math.abs(point.x - relativeX) < Math.abs(best.x - relativeX) ? point : best;
    }, null);
    if (!nearest) return;

    const nearbyAlerts = markerAlerts.filter((alert) => {
      const diff = Math.abs(new Date(alert.last_seen_at).getTime() - nearest.rawTs);
      return diff <= Math.max((maxTs - minTs) / 80, 60 * 1000);
    });

    tooltip.innerHTML = `
      <div><strong>${formatDateTime(nearest.timestamp)}</strong></div>
      <div>Valor real: ${formatMaybe(nearest.value, unit)}</div>
      <div>${trend.target_label || "Setpoint"}: ${formatMaybe(nearest.target_value, unit)}</div>
      <div>Limite inferior: ${formatMaybe(nearest.lower_limit, unit)}</div>
      <div>Limite superior: ${formatMaybe(nearest.upper_limit, unit)}</div>
      <div>Media 15 min: ${formatMaybe(nearest.rolling_mean, unit)}</div>
      <div>EWMA: ${formatMaybe(nearest.ewma, unit)}</div>
      <div>Eventos no ponto: ${formatNumber(nearbyAlerts.length, 0)}</div>
    `;
    tooltip.style.left = `${event.clientX - bounds.left}px`;
    tooltip.style.top = `${event.clientY - bounds.top}px`;
    tooltip.classList.add("visible");
  };
}

function renderAll() {
  ensureSignalSelection();
  renderTopbar();
  renderSubsystemPills();
  renderPresetButtons();
  populateSelects();
  renderOperationalPanel();
  renderScorePanel();
  renderContextPanel();
  renderQualityPanel();
  renderAlertPanels();
  renderSignalExplorer();
}

async function loadTrend() {
  if (!state.signal) return;
  const currentRequestId = ++state.trendRequestId;
  const currentSignal = state.signal;
  const params = new URLSearchParams({
    signal: currentSignal,
    range_value: String(state.rangeValue),
    range_unit: state.rangeUnit,
    bucket: state.bucket,
  });
  try {
    const trendResponse = await fetchJson(`/status/trend?${params.toString()}`);
    if (currentRequestId !== state.trendRequestId || currentSignal !== state.signal) {
      return;
    }
    state.trend = trendResponse;
    renderContextPanel();
    renderTrendSummary();
    renderChart();
  } catch (error) {
    if (currentRequestId !== state.trendRequestId) {
      return;
    }
    document.getElementById("trend-title").textContent = "Falha ao atualizar o grafico";
    document.getElementById("trend-subtitle").textContent = String(error);
    document.getElementById("trend-chart").innerHTML = "";
  }
}

async function loadBaseData() {
  const [catalogData, statusData, snapshotData, scoresData, activeData, recentData] = await Promise.all([
    fetchJson("/status/catalog"),
    fetchJson("/status"),
    fetchJson("/status/current"),
    fetchJson("/status/scores"),
    fetchJson("/alerts"),
    fetchJson("/alerts/recent?limit=5000"),
  ]);

  state.catalog = catalogData;
  state.status = statusData;
  state.snapshot = snapshotData;
  state.scores = safeArray(scoresData.scores);
  state.activeAlerts = safeArray(activeData.alerts);
  state.recentAlerts = safeArray(recentData.alerts);

  if (!state.signal) {
    state.signal = state.catalog?.default_signal || null;
  }
}

async function refreshDashboard() {
  await loadBaseData();
  renderAll();
  await loadTrend();
}

function attachEvents() {
  document.getElementById("signal-select").addEventListener("change", async (event) => {
    await focusSignal(event.target.value);
  });

  document.getElementById("severity-select").addEventListener("change", () => {
    state.severity = document.getElementById("severity-select").value;
    renderOperationalPanel();
    renderAlertPanels();
    renderSignalExplorer();
    renderScorePanel();
    renderChart();
  });

  document.getElementById("search-input").addEventListener("input", async () => {
    state.search = document.getElementById("search-input").value.trim();
    ensureSignalSelection();
    renderAll();
    setTrendLoading();
    await loadTrend();
  });

  document.getElementById("range-value").addEventListener("change", async () => {
    state.rangeValue = Number(document.getElementById("range-value").value || 1);
    renderPresetButtons();
    setTrendLoading();
    await loadTrend();
  });

  document.getElementById("range-unit").addEventListener("change", async () => {
    state.rangeUnit = document.getElementById("range-unit").value;
    renderPresetButtons();
    setTrendLoading();
    await loadTrend();
  });

  document.getElementById("bucket-select").addEventListener("change", async () => {
    state.bucket = document.getElementById("bucket-select").value;
    renderPresetButtons();
    setTrendLoading();
    await loadTrend();
  });

  document.getElementById("refresh-button").addEventListener("click", async () => {
    await refreshDashboard();
  });
}

async function bootstrap() {
  attachEvents();
  try {
    await refreshDashboard();
  } catch (error) {
    document.getElementById("hero-status").textContent = "Falha ao carregar o painel";
    document.getElementById("hero-description").textContent = String(error);
    document.getElementById("recent-alert-list").innerHTML = `<div class="empty-state">${String(error)}</div>`;
  }
  setInterval(async () => {
    try {
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    }
  }, 60000);
}

bootstrap();
