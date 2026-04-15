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

const ALERT_TYPE_LABELS = {
  all: "todos",
  fixed_rule: "fora da regra",
  trend: "comportamento/tendencia anormal",
  operational_anomaly: "anomalia operacional",
  predictive_statistics: "risco antecipado",
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

const CHART_COLORS = ["#39c7c2", "#f0c75a", "#6fa3ff", "#f29a56", "#79d08e", "#f16d6d"];
const MAX_CHART_SIGNALS = 4;
const RECENT_ALERT_FETCH_LIMIT = 5000;

const state = {
  catalog: null,
  status: null,
  snapshot: null,
  aiStatus: null,
  scores: [],
  activeAlerts: [],
  recentAlerts: [],
  trends: null,
  subsystem: "all",
  layer: "all",
  severity: "all",
  signal: null,
  selectedSignals: [],
  rangeValue: 24,
  rangeUnit: "hours",
  bucket: "hours",
  chartMode: "real",
  search: "",
  trendRequestId: 0,
  expandedDiagnoses: {},
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function uniqueTexts(items) {
  const unique = [];
  const seen = new Set();
  safeArray(items).forEach((item) => {
    const text = String(item || "").trim();
    if (!text) return;
    const key = text.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    unique.push(text);
  });
  return unique;
}

function cleanAiText(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  if (!text.startsWith("{")) return text;
  try {
    const parsed = JSON.parse(text);
    return parsed.summary || text;
  } catch (_error) {
    const match = text.match(/"summary"\s*:\s*"([^"]+)/);
    return match ? match[1] : text;
  }
}

function friendlySubsystem(value) {
  return SUBSYSTEM_LABELS[value] || String(value || "--");
}

function severityLabel(severity) {
  return SEVERITY_LABELS[String(severity || "all").toLowerCase()] || String(severity || "--");
}

function severityClass(severity) {
  return `severity-${String(severity || "all").toLowerCase()}`;
}

function layerLabel(layer) {
  return ALERT_TYPE_LABELS[String(layer || "").toLowerCase()] || String(layer || "--");
}

function severityWeight(severity) {
  const map = { low: 1, medium: 2, high: 3, critical: 4 };
  return map[String(severity || "").toLowerCase()] || 0;
}

function scoreColor(score) {
  if (score >= 80) return "#f16d6d";
  if (score >= 60) return "#f29a56";
  if (score >= 35) return "#f0c75a";
  return "#79d08e";
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

function formatAxisDate(value, rangeUnit = state.rangeUnit, bucket = state.bucket) {
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
      if (Number(right.is_setpoint) !== Number(left.is_setpoint)) return Number(left.is_setpoint) - Number(right.is_setpoint);
      return left.label.localeCompare(right.label, "pt-BR");
    });
}

function getCatalogSignals() {
  return safeArray(state.catalog?.signals).map((item) => item.signal);
}

function ensureSignalSelection() {
  const visible = getVisibleSignals();
  const allSignals = safeArray(state.catalog?.signals);
  if (!allSignals.length) {
    state.signal = null;
    state.selectedSignals = [];
    return;
  }

  const currentVisible = visible.some((item) => item.signal === state.signal);
  const currentKnown = allSignals.some((item) => item.signal === state.signal);
  if (!state.signal || !currentKnown || (state.subsystem !== "all" && !currentVisible)) {
    const nextSignal = visible.find((item) => item.active_alerts > 0) || visible[0] || allSignals[0];
    state.signal = nextSignal.signal;
  }

  const availableSignals = new Set(getCatalogSignals());
  const visibleSignals = new Set(visible.map((item) => item.signal));
  const retainedSignals = state.selectedSignals.filter((signal) => {
    if (!availableSignals.has(signal)) return false;
    return state.subsystem === "all" ? true : visibleSignals.has(signal);
  });
  const nextSelected = [state.signal, ...retainedSignals.filter((signal) => signal !== state.signal)];
  state.selectedSignals = nextSelected
    .filter((signal, index) => availableSignals.has(signal) && nextSelected.indexOf(signal) === index)
    .slice(0, MAX_CHART_SIGNALS);

  if (!state.selectedSignals.length && state.signal) {
    state.selectedSignals = [state.signal];
  }
}

function setSelectedSignals(signals, subsystem = null) {
  if (subsystem) {
    state.subsystem = subsystem;
  }

  const availableSignals = new Set(getCatalogSignals());
  const normalizedSignals = safeArray(signals)
    .map((signal) => String(signal || "").trim())
    .filter((signal, index, array) => signal && availableSignals.has(signal) && array.indexOf(signal) === index)
    .slice(0, MAX_CHART_SIGNALS);

  if (normalizedSignals.length) {
    state.selectedSignals = normalizedSignals;
    state.signal = normalizedSignals[0];
    return;
  }

  ensureSignalSelection();
}

function isChartSignal(signal) {
  return state.selectedSignals.includes(signal);
}

function setPrimarySignal(signal, subsystem = null) {
  setSelectedSignals([signal, ...state.selectedSignals.filter((item) => item !== signal)], subsystem);
}

function toggleChartSignal(signal) {
  if (!signal) return;
  const nextSelected = state.selectedSignals.includes(signal)
    ? state.selectedSignals.filter((item) => item !== signal)
    : [...state.selectedSignals, signal];
  setSelectedSignals(nextSelected.length ? nextSelected : [state.signal]);
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

function featureLabel(feature) {
  const map = {
    slope_15m: "ritmo de subida/queda nos ultimos 15 min",
    slope_1h: "ritmo de subida/queda na ultima hora",
    zscore_1h: "distancia do comportamento normal na ultima hora",
    ewma_gap_abs: "distancia do comportamento recente",
  };
  return map[String(feature || "").toLowerCase()] || String(feature || "--");
}

function countAlertsForSignal(signal, alerts) {
  return alerts.filter((alert) => alert.signal === signal).length;
}

function getPreferredSignals() {
  const visible = getVisibleSignals().filter((item) => !item.is_setpoint);
  if (state.subsystem === "all") {
    const overview = OVERVIEW_SIGNALS
      .map((signal) => visible.find((item) => item.signal === signal))
      .filter(Boolean);
    if (overview.length) return overview.slice(0, 4);
  }
  return visible.slice(0, 4);
}

function alertMatchesFilters(alert) {
  const matchesSubsystem = state.subsystem === "all" || alert.subsystem === state.subsystem;
  const matchesLayer = state.layer === "all" || alert.layer === state.layer;
  const matchesSeverity = state.severity === "all" || alert.severity === state.severity;
  const haystack = `${alert.title} ${alert.message} ${alert.rule_id} ${alert.subsystem} ${alert.signal || ""}`.toLowerCase();
  const matchesSearch = !state.search || haystack.includes(state.search.toLowerCase());
  return matchesSubsystem && matchesLayer && matchesSeverity && matchesSearch;
}

function sortAlerts(alerts) {
  return alerts.sort((left, right) => {
    const severityDelta = severityWeight(right.severity) - severityWeight(left.severity);
    if (severityDelta !== 0) return severityDelta;
    return new Date(right.last_seen_at) - new Date(left.last_seen_at);
  });
}

function getFilteredActiveAlerts() {
  return sortAlerts(safeArray(state.activeAlerts).filter((alert) => alertMatchesFilters(alert)));
}

function getFilteredRecentAlerts() {
  return safeArray(state.recentAlerts)
    .filter((alert) => !alert.is_active)
    .filter((alert) => alertMatchesFilters(alert))
    .sort((left, right) => new Date(right.last_seen_at) - new Date(left.last_seen_at));
}

function getSignalAlertEvents(signal) {
  const merged = [...safeArray(state.activeAlerts), ...safeArray(state.recentAlerts)];
  const unique = [];
  const seen = new Set();
  merged.forEach((alert) => {
    if (alert.signal !== signal || !alertMatchesFilters(alert)) return;
    const key = `${alert.alert_id}-${alert.last_seen_at}`;
    if (seen.has(key)) return;
    seen.add(key);
    unique.push(alert);
  });
  return unique.sort((left, right) => new Date(right.last_seen_at) - new Date(left.last_seen_at));
}

function getDiagnosisAlert() {
  const candidates = [
    ...getFilteredActiveAlerts().filter((alert) => alert.signal === state.signal && alert.prescriptive_diagnosis),
    ...getFilteredRecentAlerts().filter((alert) => alert.signal === state.signal && alert.prescriptive_diagnosis),
  ];
  if (candidates.length) return candidates[0];

  const subsystemFallback = [
    ...getFilteredActiveAlerts().filter((alert) => alert.subsystem === state.subsystem && alert.prescriptive_diagnosis),
    ...getFilteredRecentAlerts().filter((alert) => alert.subsystem === state.subsystem && alert.prescriptive_diagnosis),
  ];
  return subsystemFallback[0] || null;
}

function getTrendSeries(signal) {
  return safeArray(state.trends?.series).find((item) => item.signal === signal) || null;
}

function getPrimaryTrend() {
  return getTrendSeries(state.signal) || safeArray(state.trends?.series)[0] || null;
}

function colorForSignal(signal) {
  const index = state.selectedSignals.indexOf(signal);
  return CHART_COLORS[index >= 0 ? index % CHART_COLORS.length : 0];
}

function syncFilterInputs() {
  document.getElementById("layer-select").value = state.layer;
  document.getElementById("severity-select").value = state.severity;
  document.getElementById("range-value").value = String(state.rangeValue);
  document.getElementById("range-unit").value = state.rangeUnit;
  document.getElementById("bucket-select").value = state.bucket;
  document.getElementById("chart-mode-select").value = state.chartMode;
  Array.from(document.getElementById("signal-multiselect").options).forEach((option) => {
    option.selected = state.selectedSignals.includes(option.value);
  });
}

function renderSubsystemPills() {
  const container = document.getElementById("subsystem-pills");
  const subsystems = ["all", ...safeArray(state.catalog?.subsystems)];
  container.innerHTML = subsystems.map((subsystem) => `
    <button class="pill-button ${state.subsystem === subsystem ? "active" : ""}" data-subsystem="${subsystem}" type="button">
      ${friendlySubsystem(subsystem)}
    </button>
  `).join("");
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
}

function populateSelects() {
  const signalSelect = document.getElementById("signal-multiselect");
  signalSelect.innerHTML = getVisibleSignals().map((item) => {
    const suffix = item.is_setpoint ? " [meta]" : item.is_derived ? " [calc]" : "";
    return `<option value="${item.signal}">${item.label}${suffix} (${friendlySubsystem(item.subsystem)})</option>`;
  }).join("");

  const severitySelect = document.getElementById("severity-select");
  severitySelect.innerHTML = safeArray(state.catalog?.severities)
    .map((severity) => `<option value="${severity}">${severityLabel(severity)}</option>`)
    .join("");

  syncFilterInputs();
}

function renderSelectedSignals() {
  const container = document.getElementById("selected-signals");
  if (!state.selectedSignals.length) {
    container.innerHTML = '<div class="empty-state">Nenhum indicador foi selecionado para o grafico.</div>';
    return;
  }

  container.innerHTML = state.selectedSignals.map((signal, index) => {
    const meta = getSignalMeta(signal);
    return `
      <button class="selection-chip ${index === 0 ? "primary" : "secondary"}" data-select-signal="${signal}" type="button">
        <span>${meta?.label || signal}</span>
        <small>${index === 0 ? "principal" : "extra"}</small>
        ${state.selectedSignals.length > 1 ? `<span class="chip-remove" data-remove-signal="${signal}">x</span>` : ""}
      </button>
    `;
  }).join("");
}

function renderTopbar() {
  const snapshot = state.snapshot || {};
  const status = state.status || {};
  const aiStatus = state.aiStatus || {};
  const modeLabel = [snapshot.st_oper, snapshot.st_carga_oper].filter(Boolean).join(" - ") || "Sem modo identificado";
  document.getElementById("hero-status").textContent = modeLabel;
  document.getElementById("hero-description").textContent =
    `Leitura consolidada com ${formatNumber(status.history_rows, 0)} pontos historicos, ${formatNumber(status.active_alerts, 0)} alertas ativos e ${formatNumber(status.recent_alert_events, 0)} eventos recentes.`;
  document.getElementById("badge-source").textContent = `Fonte: ${status.data_source || "--"}`;
  document.getElementById("badge-refresh").textContent = `Atualizacao: ${formatDateTime(status.last_refresh_at)}`;
  document.getElementById("badge-range").textContent = `Cobertura: ${formatDateTime(status.earliest_timestamp)} ate ${formatDateTime(status.latest_timestamp)}`;
  document.getElementById("badge-rows").textContent = `Leituras: ${formatNumber(status.history_rows, 0)}`;
  const aiLabel = aiStatus.enabled
    ? `IA: ativa | ${formatNumber(aiStatus.attempts, 0)} chamadas | ${formatNumber(aiStatus.cache_hits, 0)} cache`
    : `IA: ${aiStatus.has_api_key ? "desativada" : "sem chave"}`;
  const aiError = aiStatus.last_error ? ` | ultimo erro: ${aiStatus.last_error}` : "";
  document.getElementById("badge-ai").textContent = `${aiLabel}${aiError}`;
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
        const targetLabel = getTargetLabel(item);
        const targetValue = getTargetValue(item, values);
        return `
          <div class="kpi-card ${activeCount ? "highlight" : ""}">
            <div class="stack-top">
              <div>
                <strong>${item.label}</strong>
                <div class="kpi-value">${formatMaybe(values[item.signal], item.unit || "")}</div>
              </div>
              <span class="severity-pill ${activeCount ? "severity-high" : "severity-all"}">${activeCount} ativos</span>
            </div>
            <div class="stack-meta">${targetLabel}: ${formatMaybe(targetValue, item.unit || "")}</div>
            <div class="stack-meta">Faixa operacional: ${formatOperatingRange(item.lower_limit, item.upper_limit, item.unit || "")}</div>
          </div>
        `;
      }).join("")
    : '<div class="empty-state">Nenhum indicador principal aparece para os filtros atuais.</div>';
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
          <div class="signal-meta">${item.rationale?.[0] || "Sem anomalia dominante no momento."}</div>
          <div class="score-caption">${item.active_alerts} alertas ativos | maior severidade: ${severityLabel(item.highest_severity || "all")}</div>
        </div>
      </div>
      <div class="score-bar"><div class="score-fill" style="width:${Math.min(100, item.score)}%"></div></div>
    </div>
  `).join("");
}

function buildDiagnosisInline(alert) {
  const diagnosis = alert.prescriptive_diagnosis;
  const predictive = alert.predictive_diagnosis;
  const llmInsight = alert.llm_insight;
  if (!diagnosis && !predictive && !llmInsight) return "";

  const isOpen = Boolean(state.expandedDiagnoses[alert.alert_id]);
  const buildList = (items, formatter) => {
    const allRows = safeArray(items);
    const rows = isOpen ? allRows : allRows.slice(0, 4);
    if (!rows.length) {
      return '<div class="stack-meta">Sem itens adicionais.</div>';
    }
    return `<ul class="diagnosis-list">${rows.map((item) => `<li>${escapeHtml(formatter(item))}</li>`).join("")}</ul>`;
  };
  const aiSummary = cleanAiText(llmInsight?.summary || "");
  const aiInsights = uniqueTexts(llmInsight?.insights)
    .map(cleanAiText)
    .filter((item) => item && item.toLowerCase() !== aiSummary.toLowerCase());
  const aiObservations = uniqueTexts(llmInsight?.observacoes).map(cleanAiText).filter(Boolean);
  const aiActions = uniqueTexts(llmInsight?.acoes_recomendadas).map(cleanAiText).filter(Boolean);

  return `
    <div class="alert-diagnosis">
      <div class="diagnosis-head">
        <div class="diagnosis-scores">
          ${predictive ? `<span class="diagnosis-score-tag">degradacao ${formatNumber(predictive.degradation_score, 0)}</span>` : ""}
          ${predictive ? `<span class="diagnosis-score-tag">confianca ${formatNumber((predictive.confidence || 0) * 100, 0)}%</span>` : ""}
          ${diagnosis ? `<span class="diagnosis-score-tag">criticidade: ${diagnosis.criticidade_base || "--"}</span>` : ""}
          ${diagnosis ? `<span class="diagnosis-score-tag">interno ${formatNumber(diagnosis.score_interno, 0)}</span>` : ""}
          ${diagnosis ? `<span class="diagnosis-score-tag">periferico ${formatNumber(diagnosis.score_periferico, 0)}</span>` : ""}
        </div>
        <button class="diagnosis-toggle" data-toggle-diagnosis="${alert.alert_id}" type="button">
          ${isOpen ? "Retrair" : "Expandir"}
        </button>
      </div>
      <div class="diagnosis-panel ${isOpen ? "open" : ""}">
        ${predictive ? `
          <div class="diagnosis-section">
            <strong>Leitura antecipada</strong>
            ${buildList([
              `${predictive.predicted_event === "possible_trip" ? "possivel trip" : "possivel alarme critico"} em ~${formatNumber(predictive.forecast_minutes, 0)} min`,
              `ritmo estimado: ${formatMaybe(predictive.slope_per_hour, "/h")}`,
              `qualidade do ajuste: ${formatNumber(predictive.regression_r2)}`,
              `consistencia da tendencia: ${formatNumber((predictive.directional_consistency || 0) * 100, 0)}%`,
            ], (item) => item)}
          </div>
        ` : ""}
        ${diagnosis ? `
          <div class="diagnosis-section">
            <strong>Hipoteses</strong>
            ${buildList(diagnosis.hipoteses, (item) => `${item.causa} (${item.tipo} | score ${formatNumber(item.score, 0)})`)}
          </div>
          <div class="diagnosis-section">
            <strong>Acoes</strong>
            ${buildList(diagnosis.acoes_recomendadas, (item) => item)}
          </div>
          <div class="diagnosis-section">
            <strong>Observacoes</strong>
            ${buildList(diagnosis.observacoes, (item) => item)}
          </div>
        ` : ""}
        ${llmInsight ? `
          <div class="diagnosis-section ai-section">
            <strong>Leitura de IA</strong>
            <div class="ai-card">
              <div class="ai-card-top">
                <span class="diagnosis-score-tag">confianca ${formatNumber((llmInsight.confidence || 0) * 100, 0)}%</span>
                <span class="diagnosis-score-tag">falso positivo: ${escapeHtml(severityLabel(llmInsight.false_positive_risk || "medium"))}</span>
              </div>
              <p class="ai-summary">${escapeHtml(aiSummary || "Sem resumo adicional.")}</p>
              ${aiInsights.length ? buildList(aiInsights, (item) => item) : ""}
            </div>
          </div>
          <div class="diagnosis-section">
            <strong>Hipoteses da IA</strong>
            ${buildList(llmInsight.hipoteses, (item) => `${item.causa} (${formatNumber((item.confianca || 0) * 100, 0)}%${item.racional ? ` | ${item.racional}` : ""})`)}
          </div>
          <div class="diagnosis-section">
            <strong>Acoes sugeridas pela IA</strong>
            ${buildList(aiActions, (item) => item)}
          </div>
          <div class="diagnosis-section">
            <strong>Cautelas e observacoes</strong>
            ${buildList(aiObservations, (item) => item)}
          </div>
        ` : ""}
      </div>
    </div>
  `;
}

function renderContextPanel() {
  const snapshot = state.snapshot || {};
  const values = snapshot.values || {};
  const trend = getPrimaryTrend();
  const signalMeta = getSignalMeta(state.signal);
  const unit = signalMeta?.unit || trend?.unit || "";
  const targetLabel = trend?.target_label || getTargetLabel(signalMeta);
  const targetValue = trend?.summary?.target_current ?? getTargetValue(signalMeta, values, trend?.target_value);
  const cards = [
    ["Indicador em foco", signalMeta?.label || "--"],
    ["Valor atual", formatMaybe(trend?.summary?.latest, unit)],
    [targetLabel, formatMaybe(targetValue, unit)],
    ["Faixa operacional", formatOperatingRange(trend?.lower_limit, trend?.upper_limit, unit)],
    ["Turno", values.ds_turno || "--"],
    ["Status", formatMaybe(values.status)],
  ];

  document.getElementById("context-grid").innerHTML = cards.map(([label, value]) => `
    <div class="context-card">
      <strong>${label}</strong>
      <div class="context-value">${value}</div>
    </div>
  `).join("");

  const rules = safeArray(trend?.rules);
  document.getElementById("rule-list").innerHTML = rules.length
    ? rules.map((rule) => `
        <div class="stack-item">
          <div class="stack-top">
            <div>
              <div class="stack-title-main">${rule.title}</div>
              <div class="stack-meta">${rule.rule_id} | ${layerLabel(rule.layer)}</div>
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
          <div class="stack-top">
            <div>
              <div class="stack-title-main">${issue.issue_type}</div>
              <div class="stack-meta">${issue.signal || "geral"}</div>
            </div>
          </div>
          <div class="stack-meta">${issue.message}</div>
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
              <div class="stack-meta">${friendlySubsystem(alert.subsystem)} | ${alert.signal || "--"} | ${layerLabel(alert.layer)} | ${alert.rule_id}</div>
            </div>
            <span class="severity-pill ${severityClass(alert.severity)}">${severityLabel(alert.severity)}</span>
          </div>
          <div class="stack-meta">${alert.message}</div>
          ${buildAlertFooter(alert)}
          ${buildDiagnosisInline(alert)}
        </div>
      `).join("")
    : `<div class="empty-state">${emptyText}</div>`;
}

function buildAlertFooter(alert) {
  const metadata = alert.metadata || {};
  if (alert.layer === "trend" && metadata.feature) {
    const referenceLabel = metadata.reference_label || "referencia recente";
    const analysisLabel = metadata.analysis_label || "comportamento anormal";
    const analysisReason = metadata.analysis_reason ? ` | leitura: ${metadata.analysis_reason}` : "";
    return `
      <div class="stack-footer">
        Valor do sinal: ${formatMaybe(metadata.signal_value ?? alert.current_value)}
        | ${referenceLabel}: ${formatMaybe(metadata.reference_value)}
        | ${analysisLabel}: ${featureLabel(metadata.feature)} (${formatMaybe(metadata.feature_value)})
        ${analysisReason}
        | ultima ocorrencia: ${formatDateTime(alert.last_seen_at)}
      </div>
    `;
  }
  if (alert.layer === "predictive_statistics" && alert.predictive_diagnosis) {
    return `
      <div class="stack-footer">
        Valor atual: ${formatMaybe(alert.current_value)}
        | confianca: ${formatNumber((alert.predictive_diagnosis.confidence || 0) * 100, 0)}%
        | evento previsto: ${alert.predictive_diagnosis.predicted_event === "possible_trip" ? "possivel trip" : "alarme critico"}
        | horizonte: ${formatNumber(alert.predictive_diagnosis.forecast_minutes, 0)} min
      </div>
    `;
  }
  return `<div class="stack-footer">Valor: ${formatMaybe(alert.current_value)} | Ultima ocorrencia: ${formatDateTime(alert.last_seen_at)}</div>`;
}

function renderAlertPanels() {
  renderAlertList(
    "recent-alert-list",
    getFilteredRecentAlerts().slice(0, 120),
    "Nenhum evento historico encontrado dentro dos filtros escolhidos.",
    "recent-count",
  );
  renderAlertList(
    "active-alert-list",
    getFilteredActiveAlerts().slice(0, 120),
    "Nenhum alerta ativo para os filtros atuais.",
    "active-count",
  );
}

function renderSignalExplorer() {
  const container = document.getElementById("signal-list");
  const visibleSignals = getVisibleSignals();
  document.getElementById("signal-panel-note").textContent =
    `${friendlySubsystem(state.subsystem)} | ${formatNumber(visibleSignals.length, 0)} sinais visiveis`;

  const values = state.snapshot?.values || {};
  const activeAlerts = safeArray(state.activeAlerts);
  const recentAlerts = safeArray(state.recentAlerts);
  container.innerHTML = visibleSignals.length
    ? visibleSignals.map((item) => {
        const activeCount = countAlertsForSignal(item.signal, activeAlerts);
        const recentCount = countAlertsForSignal(item.signal, recentAlerts);
        const chartSelected = isChartSignal(item.signal);
        const isPrimary = state.signal === item.signal;
        const targetValue = getTargetValue(item, values);
        const targetLabel = getTargetLabel(item);
        return `
          <div class="signal-item ${state.signal === item.signal ? "focused" : ""}">
            <div class="signal-top">
              <div>
                <div class="signal-title">${item.label}</div>
                <div class="signal-subvalue">${formatMaybe(values[item.signal], item.unit || "")}</div>
              </div>
              <span class="severity-pill ${activeCount ? "severity-high" : recentCount ? "severity-medium" : "severity-all"}">
                ${activeCount ? `${activeCount} ativos` : `${recentCount} eventos`}
              </span>
            </div>
            <div class="signal-meta">${friendlySubsystem(item.subsystem)} | ${item.signal}${item.is_setpoint ? " | meta" : item.is_derived ? " | calculado" : ""}</div>
            <div class="signal-footer">${targetLabel}: ${formatMaybe(targetValue, item.unit || "")} | Faixa: ${formatOperatingRange(item.lower_limit, item.upper_limit, item.unit || "")}</div>
            <div class="signal-actions">
              <button class="mini-button ${isPrimary ? "active" : ""}" data-focus-signal="${item.signal}" data-focus-subsystem="${item.subsystem}" type="button">
                ${isPrimary ? "Em foco" : "Focar"}
              </button>
              <button class="mini-button secondary ${chartSelected ? "active" : ""}" ${isPrimary ? "disabled" : `data-toggle-signal="${item.signal}"`} type="button">
                ${isPrimary ? "Principal" : chartSelected ? "No grafico" : "Correlacionar"}
              </button>
            </div>
          </div>
        `;
      }).join("")
    : '<div class="empty-state">Nenhum sinal corresponde aos filtros atuais.</div>';
}

function renderTrendSummary() {
  const trend = getPrimaryTrend();
  const unit = trend?.unit || "";
  const targetLabel = trend?.target_label || "Setpoint";
  const cards = [
    ["Valor atual", formatMaybe(trend?.summary?.latest, unit)],
    [targetLabel, formatMaybe(trend?.summary?.target_current ?? trend?.target_value, unit)],
    ["Faixa operacional", formatOperatingRange(trend?.lower_limit, trend?.upper_limit, unit)],
    ["Media da janela", formatMaybe(trend?.summary?.mean, unit)],
    ["Tendencia 15 min", formatMaybe(trend?.summary?.slope_15m, unit ? `${unit}/min` : "")],
    ["Z-score 1h", formatMaybe(trend?.summary?.zscore_1h)],
  ];

  document.getElementById("trend-summary-grid").innerHTML = cards.map(([label, value]) => `
    <div class="context-card">
      <strong>${label}</strong>
      <div class="context-value">${value}</div>
    </div>
  `).join("");
}

function renderTrendLegend(series = [], mode = "single") {
  const container = document.getElementById("trend-legend");
  if (mode === "correlation") {
    container.innerHTML = series.map((item) => `
      <span><i class="legend-line" style="background:${colorForSignal(item.signal)}"></i>${item.label}</span>
    `).join("");
    return;
  }

  container.innerHTML = `
    <span><i class="legend-line legend-actual"></i>Valor real</span>
    <span><i class="legend-line legend-target"></i>Setpoint</span>
    <span><i class="legend-line legend-upper"></i>Limite superior</span>
    <span><i class="legend-line legend-lower"></i>Limite inferior</span>
    <span><i class="legend-line legend-mean"></i>Media 15 min</span>
    <span><i class="legend-line legend-ewma"></i>EWMA</span>
    <span><i class="legend-dot legend-alert"></i>Eventos</span>
  `;
}

function buildPath(points, xKey, yKey) {
  const filtered = points.filter((point) => point[yKey] !== null && point[yKey] !== undefined);
  if (!filtered.length) return "";
  return filtered.map((point, index) => `${index === 0 ? "M" : "L"} ${point[xKey]} ${point[yKey]}`).join(" ");
}

function getMarkerColor(severity) {
  const map = {
    low: "#79d08e",
    medium: "#f0c75a",
    high: "#f29a56",
    critical: "#f16d6d",
  };
  return map[String(severity || "").toLowerCase()] || "#f0c75a";
}

function setTrendLoading() {
  document.getElementById("trend-title").textContent = "Atualizando leitura temporal...";
  document.getElementById("trend-subtitle").textContent = "Recalculando curvas e correlacoes.";
  document.getElementById("trend-chart").innerHTML = "";
  document.getElementById("chart-tooltip").classList.remove("visible");
}

function buildGridLines(width, height, margin, minValue, maxValue, formatter = formatNumber) {
  const lines = [];
  const tickCount = 4;
  for (let step = 0; step <= tickCount; step += 1) {
    const y = margin.top + ((height - margin.top - margin.bottom) / tickCount) * step;
    const value = maxValue - ((maxValue - minValue) / tickCount) * step;
    lines.push(`
      <line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" stroke="rgba(255,255,255,0.07)" stroke-dasharray="4 8" />
      <text x="${margin.left - 10}" y="${y + 4}" fill="rgba(174,181,192,0.95)" font-size="12" text-anchor="end" font-family="Aptos, Segoe UI, Arial, sans-serif">${formatter(value)}</text>
    `);
  }
  return lines.join("");
}

function buildXTicks(minTs, maxTs, width, height, margin, rangeUnit, bucket) {
  const plotWidth = width - margin.left - margin.right;
  const xScale = (value) => {
    if (maxTs === minTs) return margin.left + plotWidth / 2;
    return margin.left + ((value - minTs) / (maxTs - minTs)) * plotWidth;
  };

  const ticks = [];
  for (let index = 0; index < 5; index += 1) {
    const ts = minTs + ((maxTs - minTs) / 4) * index;
    ticks.push(`
      <text x="${xScale(ts)}" y="${height - 14}" fill="rgba(174,181,192,0.95)" font-size="12" text-anchor="middle" font-family="Aptos, Segoe UI, Arial, sans-serif">${formatAxisDate(ts, rangeUnit, bucket)}</text>
    `);
  }
  return ticks.join("");
}

function renderPrimaryChart() {
  const svg = document.getElementById("trend-chart");
  const tooltip = document.getElementById("chart-tooltip");
  const trend = getPrimaryTrend();
  const points = safeArray(trend?.points);
  const title = document.getElementById("trend-title");
  const subtitle = document.getElementById("trend-subtitle");

  if (!trend || !points.length) {
    title.textContent = "Sem dados suficientes para o indicador atual";
    subtitle.textContent = "A serie temporal ficou vazia para a janela escolhida.";
    svg.innerHTML = "";
    tooltip.classList.remove("visible");
    renderTrendLegend([], "single");
    return;
  }

  title.textContent = `${trend.label}`;
  subtitle.textContent = `${friendlySubsystem(trend.subsystem)} | ${points.length} pontos | janela ${trend.range_value} ${trend.range_unit} | agrupamento ${trend.bucket}`;
  renderTrendLegend([trend], "single");

  const width = 1040;
  const height = 380;
  const margin = { top: 22, right: 24, bottom: 46, left: 72 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const timestamps = points.map((point) => new Date(point.timestamp).getTime()).filter(Number.isFinite);
  if (!timestamps.length) {
    svg.innerHTML = "";
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
    svg.innerHTML = "";
    return;
  }

  const rawMin = Math.min(...numericValues);
  const rawMax = Math.max(...numericValues);
  const padding = rawMin === rawMax ? Math.max(Math.abs(rawMax), 1) * 0.15 : (rawMax - rawMin) * 0.15;
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

  const lastPoint = chartPoints[chartPoints.length - 1];
  const bandMarkup = (lastPoint.lower_limit !== null && lastPoint.lower_limit !== undefined
    && lastPoint.upper_limit !== null && lastPoint.upper_limit !== undefined)
    ? `<rect x="${margin.left}" y="${yScale(Number(lastPoint.upper_limit))}" width="${plotWidth}" height="${yScale(Number(lastPoint.lower_limit)) - yScale(Number(lastPoint.upper_limit))}" fill="rgba(57,199,194,0.08)" rx="14" />`
    : "";

  const markerAlerts = getSignalAlertEvents(trend.signal).filter((alert) => {
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
    const y = nearestPoint?.y ?? margin.top + 20;
    const color = getMarkerColor(alert.severity);
    return `
      <line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" stroke="${color}" stroke-opacity="0.18" stroke-dasharray="4 8" />
      <circle cx="${x}" cy="${y}" r="4.5" fill="${color}" stroke="#0e141a" stroke-width="2" />
    `;
  }).join("");

  svg.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" />
    ${bandMarkup}
    ${buildGridLines(width, height, margin, minValue, maxValue)}
    <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(255,255,255,0.12)" />
    ${markerMarkup}
    <path d="${buildPath(chartPoints, "x", "targetY")}" fill="none" stroke="#f0c65a" stroke-width="2" stroke-dasharray="8 7" stroke-linecap="round" />
    <path d="${buildPath(chartPoints, "x", "upperY")}" fill="none" stroke="#ef9a56" stroke-width="1.8" stroke-dasharray="4 6" />
    <path d="${buildPath(chartPoints, "x", "lowerY")}" fill="none" stroke="#77d28f" stroke-width="1.8" stroke-dasharray="4 6" />
    <path d="${buildPath(chartPoints, "x", "meanY")}" fill="none" stroke="#78a5ff" stroke-width="2" />
    <path d="${buildPath(chartPoints, "x", "ewmaY")}" fill="none" stroke="#c16f39" stroke-width="2" stroke-dasharray="6 6" />
    <path d="${buildPath(chartPoints, "x", "y")}" fill="none" stroke="#39c7c2" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="${lastPoint.x}" cy="${lastPoint.y ?? margin.top + plotHeight / 2}" r="5" fill="#39c7c2" />
    ${buildXTicks(minTs, maxTs, width, height, margin, trend.range_unit, trend.bucket)}
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
      <div>Valor real: ${formatMaybe(nearest.value, trend.unit || "")}</div>
      <div>${trend.target_label || "Setpoint"}: ${formatMaybe(nearest.target_value, trend.unit || "")}</div>
      <div>Limite inferior: ${formatMaybe(nearest.lower_limit, trend.unit || "")}</div>
      <div>Limite superior: ${formatMaybe(nearest.upper_limit, trend.unit || "")}</div>
      <div>Media 15 min: ${formatMaybe(nearest.rolling_mean, trend.unit || "")}</div>
      <div>EWMA: ${formatMaybe(nearest.ewma, trend.unit || "")}</div>
      <div>Eventos no ponto: ${formatNumber(nearbyAlerts.length, 0)}</div>
    `;
    tooltip.style.left = `${event.clientX - bounds.left}px`;
    tooltip.style.top = `${event.clientY - bounds.top}px`;
    tooltip.classList.add("visible");
  };
}

function normalizeSeries(series) {
  const rawValues = safeArray(series.points).map((point) => Number(point.value)).filter(Number.isFinite);
  if (!rawValues.length) return [];
  const minValue = Math.min(...rawValues);
  const maxValue = Math.max(...rawValues);
  return safeArray(series.points).map((point) => {
    const value = Number(point.value);
    if (!Number.isFinite(value)) {
      return { ...point, normalized: null, rawTs: new Date(point.timestamp).getTime() };
    }
    const normalized = maxValue === minValue ? 50 : ((value - minValue) / (maxValue - minValue)) * 100;
    return {
      ...point,
      normalized,
      rawTs: new Date(point.timestamp).getTime(),
    };
  });
}

function renderRealMultiChart() {
  const svg = document.getElementById("trend-chart");
  const tooltip = document.getElementById("chart-tooltip");
  const series = state.selectedSignals
    .map((signal) => getTrendSeries(signal))
    .filter((item) => item && safeArray(item.points).length);

  if (!series.length) {
    document.getElementById("trend-title").textContent = "Sem dados suficientes para a selecao atual";
    document.getElementById("trend-subtitle").textContent = "Nenhuma serie temporal foi retornada para os indicadores selecionados.";
    svg.innerHTML = "";
    tooltip.classList.remove("visible");
    return;
  }

  document.getElementById("trend-title").textContent = `Modo real com ${series.length} indicadores`;
  document.getElementById("trend-subtitle").textContent =
    "Curvas nas unidades originais. Use esse modo para leitura fisica e o modo normalizado para comparar comportamento relativo.";
  renderTrendLegend(series, "correlation");

  const width = 1040;
  const height = 380;
  const margin = { top: 22, right: 24, bottom: 46, left: 72 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const timestamps = series
    .flatMap((item) => safeArray(item.points).map((point) => new Date(point.timestamp).getTime()))
    .filter(Number.isFinite);
  if (!timestamps.length) {
    svg.innerHTML = "";
    return;
  }

  const numericValues = series
    .flatMap((item) => safeArray(item.points).map((point) => Number(point.value)))
    .filter(Number.isFinite);
  if (!numericValues.length) {
    svg.innerHTML = "";
    return;
  }

  const minTs = Math.min(...timestamps);
  const maxTs = Math.max(...timestamps);
  const xScale = (value) => {
    if (maxTs === minTs) return margin.left + plotWidth / 2;
    return margin.left + ((value - minTs) / (maxTs - minTs)) * plotWidth;
  };

  const rawMin = Math.min(...numericValues);
  const rawMax = Math.max(...numericValues);
  const padding = rawMin === rawMax ? Math.max(Math.abs(rawMax), 1) * 0.15 : (rawMax - rawMin) * 0.15;
  const minValue = rawMin - padding;
  const maxValue = rawMax + padding;
  const yScale = (value) => {
    if (maxValue === minValue) return margin.top + plotHeight / 2;
    return margin.top + plotHeight - ((value - minValue) / (maxValue - minValue)) * plotHeight;
  };

  const projectedSeries = series.map((item) => ({
    ...item,
    color: colorForSignal(item.signal),
    chartPoints: safeArray(item.points).map((point) => {
      const rawTs = new Date(point.timestamp).getTime();
      const value = Number(point.value);
      return {
        ...point,
        rawTs,
        x: xScale(rawTs),
        y: Number.isFinite(value) ? yScale(value) : null,
      };
    }),
  }));

  const primary = getPrimaryTrend();
  const markerAlerts = primary
    ? getSignalAlertEvents(primary.signal).filter((alert) => {
        const ts = new Date(alert.last_seen_at).getTime();
        return Number.isFinite(ts) && ts >= minTs && ts <= maxTs;
      }).slice(0, 80)
    : [];

  const markerMarkup = markerAlerts.map((alert) => {
    const ts = new Date(alert.last_seen_at).getTime();
    const x = xScale(ts);
    return `<line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" stroke="${getMarkerColor(alert.severity)}" stroke-opacity="0.12" stroke-dasharray="4 8" />`;
  }).join("");

  svg.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" />
    ${buildGridLines(width, height, margin, minValue, maxValue)}
    <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(255,255,255,0.12)" />
    ${markerMarkup}
    ${projectedSeries.map((item) => `
      <path d="${buildPath(item.chartPoints, "x", "y")}" fill="none" stroke="${item.color}" stroke-width="${item.signal === state.signal ? 3.3 : 2.2}" stroke-linecap="round" stroke-linejoin="round" />
    `).join("")}
    ${buildXTicks(minTs, maxTs, width, height, margin, state.rangeUnit, state.bucket)}
  `;

  svg.onmouseleave = () => tooltip.classList.remove("visible");
  svg.onmousemove = (event) => {
    const bounds = svg.getBoundingClientRect();
    const relativeX = ((event.clientX - bounds.left) / bounds.width) * width;
    const summaries = projectedSeries.map((item) => {
      const nearest = item.chartPoints.reduce((best, point) => {
        if (!best) return point;
        return Math.abs(point.x - relativeX) < Math.abs(best.x - relativeX) ? point : best;
      }, null);
      return nearest ? {
        label: item.label,
        unit: item.unit,
        color: item.color,
        value: nearest.value,
        timestamp: nearest.timestamp,
      } : null;
    }).filter(Boolean);

    if (!summaries.length) return;
    tooltip.innerHTML = `
      <div><strong>${formatDateTime(summaries[0].timestamp)}</strong></div>
      ${summaries.map((item) => `
        <div style="color:${item.color}">${item.label}: ${formatMaybe(item.value, item.unit || "")}</div>
      `).join("")}
    `;
    tooltip.style.left = `${event.clientX - bounds.left}px`;
    tooltip.style.top = `${event.clientY - bounds.top}px`;
    tooltip.classList.add("visible");
  };
}

function renderCorrelationChart() {
  const svg = document.getElementById("trend-chart");
  const tooltip = document.getElementById("chart-tooltip");
  const series = state.selectedSignals
    .map((signal) => getTrendSeries(signal))
    .filter((item) => item && safeArray(item.points).length);

  if (!series.length) {
    document.getElementById("trend-title").textContent = "Sem dados suficientes para a selecao atual";
    document.getElementById("trend-subtitle").textContent = "Nenhuma serie temporal foi retornada para os indicadores selecionados.";
    svg.innerHTML = "";
    tooltip.classList.remove("visible");
    return;
  }

  document.getElementById("trend-title").textContent = `Correlacao de ${series.length} indicadores`;
  document.getElementById("trend-subtitle").textContent =
    "Curvas normalizadas na mesma escala para comparar comportamento relativo entre indicadores com unidades diferentes.";
  renderTrendLegend(series, "correlation");

  const width = 1040;
  const height = 380;
  const margin = { top: 22, right: 24, bottom: 46, left: 72 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const timestamps = series
    .flatMap((item) => safeArray(item.points).map((point) => new Date(point.timestamp).getTime()))
    .filter(Number.isFinite);
  if (!timestamps.length) {
    svg.innerHTML = "";
    return;
  }
  const minTs = Math.min(...timestamps);
  const maxTs = Math.max(...timestamps);
  const xScale = (value) => {
    if (maxTs === minTs) return margin.left + plotWidth / 2;
    return margin.left + ((value - minTs) / (maxTs - minTs)) * plotWidth;
  };
  const yScale = (value) => margin.top + plotHeight - (value / 100) * plotHeight;

  const normalizedSeries = series.map((item) => ({
    ...item,
    color: colorForSignal(item.signal),
    normalizedPoints: normalizeSeries(item).map((point) => ({
      ...point,
      x: xScale(point.rawTs),
      y: point.normalized === null ? null : yScale(point.normalized),
    })),
  }));

  const primary = getPrimaryTrend();
  const markerAlerts = primary
    ? getSignalAlertEvents(primary.signal).filter((alert) => {
        const ts = new Date(alert.last_seen_at).getTime();
        return Number.isFinite(ts) && ts >= minTs && ts <= maxTs;
      }).slice(0, 80)
    : [];

  const markerMarkup = markerAlerts.map((alert) => {
    const ts = new Date(alert.last_seen_at).getTime();
    const x = xScale(ts);
    return `<line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" stroke="${getMarkerColor(alert.severity)}" stroke-opacity="0.12" stroke-dasharray="4 8" />`;
  }).join("");

  svg.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" />
    ${buildGridLines(width, height, margin, 0, 100, (value) => `${formatNumber(value, 0)}%`)}
    <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(255,255,255,0.12)" />
    ${markerMarkup}
    ${normalizedSeries.map((item) => `
      <path d="${buildPath(item.normalizedPoints, "x", "y")}" fill="none" stroke="${item.color}" stroke-width="${item.signal === state.signal ? 3.3 : 2.4}" stroke-linecap="round" stroke-linejoin="round" />
    `).join("")}
    ${buildXTicks(minTs, maxTs, width, height, margin, state.rangeUnit, state.bucket)}
  `;

  svg.onmouseleave = () => tooltip.classList.remove("visible");
  svg.onmousemove = (event) => {
    const bounds = svg.getBoundingClientRect();
    const relativeX = ((event.clientX - bounds.left) / bounds.width) * width;
    const summaries = normalizedSeries.map((item) => {
      const nearest = item.normalizedPoints.reduce((best, point) => {
        if (!best) return point;
        return Math.abs(point.x - relativeX) < Math.abs(best.x - relativeX) ? point : best;
      }, null);
      return nearest ? {
        label: item.label,
        unit: item.unit,
        color: item.color,
        value: nearest.value,
        normalized: nearest.normalized,
        timestamp: nearest.timestamp,
      } : null;
    }).filter(Boolean);

    if (!summaries.length) return;
    tooltip.innerHTML = `
      <div><strong>${formatDateTime(summaries[0].timestamp)}</strong></div>
      ${summaries.map((item) => `
        <div style="color:${item.color}">${item.label}: ${formatMaybe(item.value, item.unit || "")} | indice ${formatNumber(item.normalized, 0)}%</div>
      `).join("")}
    `;
    tooltip.style.left = `${event.clientX - bounds.left}px`;
    tooltip.style.top = `${event.clientY - bounds.top}px`;
    tooltip.classList.add("visible");
  };
}

function renderCharts() {
  renderTrendSummary();
  if (state.selectedSignals.length > 1) {
    if (state.chartMode === "normalized") {
      renderCorrelationChart();
      return;
    }
    renderRealMultiChart();
    return;
  }
  renderPrimaryChart();
}

function bindDynamicEvents() {
  document.querySelectorAll("[data-subsystem]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", async () => {
      state.subsystem = button.dataset.subsystem;
      ensureSignalSelection();
      renderAll();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-range-value]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", async () => {
      state.rangeValue = Number(button.dataset.rangeValue);
      state.rangeUnit = button.dataset.rangeUnit;
      state.bucket = button.dataset.bucket;
      syncFilterInputs();
      renderPresetButtons();
      bindDynamicEvents();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-score-subsystem]").forEach((element) => {
    if (element.dataset.bound === "1") return;
    element.dataset.bound = "1";
    element.addEventListener("click", async () => {
      state.subsystem = element.dataset.scoreSubsystem;
      ensureSignalSelection();
      renderAll();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-select-signal]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", async (event) => {
      const removeSignal = event.target.dataset.removeSignal;
      if (removeSignal) {
        event.stopPropagation();
        toggleChartSignal(removeSignal);
      } else {
        setPrimarySignal(button.dataset.selectSignal);
      }
      renderAll();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-alert-signal]").forEach((element) => {
    if (element.dataset.bound === "1") return;
    element.dataset.bound = "1";
    element.addEventListener("click", async () => {
      const nextSignal = element.dataset.alertSignal;
      const nextSubsystem = element.dataset.alertSubsystem;
      if (!nextSignal) return;
      setPrimarySignal(nextSignal, nextSubsystem || null);
      renderAll();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-focus-signal]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", async () => {
      setPrimarySignal(button.dataset.focusSignal, button.dataset.focusSubsystem || null);
      renderAll();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-toggle-signal]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      toggleChartSignal(button.dataset.toggleSignal);
      renderAll();
      setTrendLoading();
      await loadTrends();
    });
  });

  document.querySelectorAll("[data-toggle-diagnosis]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const alertId = button.dataset.toggleDiagnosis;
      state.expandedDiagnoses[alertId] = !state.expandedDiagnoses[alertId];
      renderAlertPanels();
      bindDynamicEvents();
    });
  });
}

function renderAll() {
  ensureSignalSelection();
  renderTopbar();
  renderSubsystemPills();
  renderPresetButtons();
  populateSelects();
  renderSelectedSignals();
  renderOperationalPanel();
  renderScorePanel();
  renderContextPanel();
  renderAlertPanels();
  renderSignalExplorer();
  renderQualityPanel();
  bindDynamicEvents();
}

function getTrendPointBudget() {
  if (state.bucket === "raw" && state.rangeUnit === "days") return 420;
  if (state.bucket === "raw" && state.rangeUnit === "hours") return 520;
  if (state.bucket === "raw" && state.rangeUnit === "minutes") return 360;
  if (state.bucket === "minutes") return 700;
  if (state.bucket === "hours") return 600;
  return 400;
}

async function loadTrends() {
  ensureSignalSelection();
  if (!state.selectedSignals.length) return;

  const currentRequestId = ++state.trendRequestId;
  const selectedAtRequest = [...state.selectedSignals];
  const params = new URLSearchParams({
    range_value: String(state.rangeValue),
    range_unit: state.rangeUnit,
    bucket: state.bucket,
    max_points: String(getTrendPointBudget()),
  });
  selectedAtRequest.forEach((signal) => params.append("signals", signal));

  try {
    const trendResponse = await fetchJson(`/status/trends?${params.toString()}`);
    const sameSelection = selectedAtRequest.length === state.selectedSignals.length
      && selectedAtRequest.every((signal, index) => signal === state.selectedSignals[index]);
    if (currentRequestId !== state.trendRequestId || !sameSelection) {
      return;
    }
    state.trends = trendResponse;
    renderContextPanel();
    renderCharts();
  } catch (error) {
    if (currentRequestId !== state.trendRequestId) return;
    document.getElementById("trend-title").textContent = "Falha ao atualizar o grafico";
    document.getElementById("trend-subtitle").textContent = String(error);
    document.getElementById("trend-chart").innerHTML = "";
  }
}

async function loadBaseData() {
  const [catalogData, statusData, snapshotData, scoresData, aiData, activeData, recentData] = await Promise.all([
    fetchJson("/status/catalog"),
    fetchJson("/status"),
    fetchJson("/status/current"),
    fetchJson("/status/scores"),
    fetchJson("/status/ai"),
    fetchJson("/alerts"),
    fetchJson(`/alerts/recent?limit=${RECENT_ALERT_FETCH_LIMIT}`),
  ]);

  state.catalog = catalogData;
  state.status = statusData;
  state.snapshot = snapshotData;
  state.aiStatus = aiData;
  state.scores = safeArray(scoresData.scores);
  state.activeAlerts = safeArray(activeData.alerts);
  state.recentAlerts = safeArray(recentData.alerts);

  if (!state.signal) {
    state.signal = state.catalog?.default_signal || null;
  }
  ensureSignalSelection();
}

async function refreshDashboard() {
  await loadBaseData();
  renderAll();
  setTrendLoading();
  await loadTrends();
}

function attachEvents() {
  document.getElementById("signal-multiselect").addEventListener("change", async (event) => {
    const selected = Array.from(event.target.selectedOptions).map((option) => option.value);
    setSelectedSignals(selected.length ? selected : [state.signal]);
    renderAll();
    setTrendLoading();
    await loadTrends();
  });

  document.getElementById("layer-select").addEventListener("change", () => {
    state.layer = document.getElementById("layer-select").value;
    renderOperationalPanel();
    renderScorePanel();
    renderContextPanel();
    renderAlertPanels();
    renderSignalExplorer();
    renderCharts();
    bindDynamicEvents();
  });

  document.getElementById("severity-select").addEventListener("change", () => {
    state.severity = document.getElementById("severity-select").value;
    renderOperationalPanel();
    renderScorePanel();
    renderContextPanel();
    renderAlertPanels();
    renderSignalExplorer();
    renderCharts();
    bindDynamicEvents();
  });

  document.getElementById("search-input").addEventListener("input", async () => {
    state.search = document.getElementById("search-input").value.trim();
    ensureSignalSelection();
    renderAll();
    setTrendLoading();
    await loadTrends();
  });

  document.getElementById("range-value").addEventListener("change", async () => {
    state.rangeValue = Number(document.getElementById("range-value").value || 1);
    renderPresetButtons();
    bindDynamicEvents();
    setTrendLoading();
    await loadTrends();
  });

  document.getElementById("range-unit").addEventListener("change", async () => {
    state.rangeUnit = document.getElementById("range-unit").value;
    renderPresetButtons();
    bindDynamicEvents();
    setTrendLoading();
    await loadTrends();
  });

  document.getElementById("bucket-select").addEventListener("change", async () => {
    state.bucket = document.getElementById("bucket-select").value;
    renderPresetButtons();
    bindDynamicEvents();
    setTrendLoading();
    await loadTrends();
  });

  document.getElementById("chart-mode-select").addEventListener("change", () => {
    state.chartMode = document.getElementById("chart-mode-select").value;
    renderCharts();
  });

  document.getElementById("chart-info-button").addEventListener("click", () => {
    const panel = document.getElementById("chart-info-panel");
    const button = document.getElementById("chart-info-button");
    const isHidden = panel.hasAttribute("hidden");
    if (isHidden) {
      panel.removeAttribute("hidden");
      button.setAttribute("aria-expanded", "true");
      return;
    }
    panel.setAttribute("hidden", "");
    button.setAttribute("aria-expanded", "false");
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
