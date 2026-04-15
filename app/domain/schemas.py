"""Schemas da API e do dominio."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DataQualityIssue(BaseModel):
    issue_type: str
    signal: str | None = None
    timestamp: datetime | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PrescriptiveHypothesis(BaseModel):
    causa: str
    tipo: str
    score: int


class PrescriptiveDiagnosis(BaseModel):
    variavel_principal: str
    subsistema: str
    flags_ativas: list[str] = Field(default_factory=list)
    score_interno: int = 0
    score_periferico: int = 0
    hipoteses: list[PrescriptiveHypothesis] = Field(default_factory=list)
    acoes_recomendadas: list[str] = Field(default_factory=list)
    criticidade_base: str
    observacoes: list[str] = Field(default_factory=list)


class LlmInsightHypothesis(BaseModel):
    causa: str
    confianca: float = 0.0
    racional: str | None = None


class LlmInsight(BaseModel):
    provider: str
    model: str
    confidence: float = 0.0
    summary: str
    insights: list[str] = Field(default_factory=list)
    observacoes: list[str] = Field(default_factory=list)
    false_positive_risk: str = "medium"
    hipoteses: list[LlmInsightHypothesis] = Field(default_factory=list)
    acoes_recomendadas: list[str] = Field(default_factory=list)


class PredictiveDiagnosis(BaseModel):
    signal: str
    method: str = "trend_regression"
    trend_direction: str
    degradation_score: float
    confidence: float
    threshold: float
    threshold_label: str
    current_value: float | None = None
    slope_per_hour: float | None = None
    zscore_1h: float | None = None
    ewma_gap_abs: float | None = None
    regression_r2: float | None = None
    directional_consistency: float | None = None
    forecast_minutes: float | None = None
    predicted_event: str
    observations: list[str] = Field(default_factory=list)


class AlertRecord(BaseModel):
    alert_id: str
    rule_id: str
    layer: str
    subsystem: str
    signal: str | None = None
    severity: str
    title: str
    message: str
    triggered_at: datetime
    last_seen_at: datetime
    current_value: float | int | str | None = None
    threshold: str | None = None
    mode_key: str
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    prescriptive_diagnosis: PrescriptiveDiagnosis | None = None
    predictive_diagnosis: PredictiveDiagnosis | None = None
    llm_insight: LlmInsight | None = None


class SubsystemRiskScore(BaseModel):
    subsystem: str
    score: float
    active_alerts: int
    highest_severity: str | None = None
    rationale: list[str] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    timestamp: datetime | None = None
    mode_key: str | None = None
    st_oper: str | None = None
    st_carga_oper: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    data_quality_issues: list[DataQualityIssue] = Field(default_factory=list)


class ReadingsResponse(BaseModel):
    count: int
    readings: list[dict[str, Any]]


class AlertsResponse(BaseModel):
    count: int
    alerts: list[AlertRecord]


class RiskScoresResponse(BaseModel):
    generated_at: datetime
    scores: list[SubsystemRiskScore]


class SignalCatalogItem(BaseModel):
    signal: str
    label: str
    subsystem: str
    unit: str | None = None
    is_setpoint: bool = False
    is_derived: bool = False
    default_target_signal: str | None = None
    default_target_label: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    target_value: float | None = None
    active_alerts: int = 0


class SignalCatalogResponse(BaseModel):
    default_signal: str | None = None
    default_window: int = 120
    subsystems: list[str] = Field(default_factory=list)
    severities: list[str] = Field(default_factory=list)
    signals: list[SignalCatalogItem] = Field(default_factory=list)


class TrendRuleSummary(BaseModel):
    rule_id: str
    title: str
    severity: str
    layer: str
    condition: str | None = None
    threshold: str | None = None


class TrendPoint(BaseModel):
    timestamp: datetime
    value: float | None = None
    target_value: float | None = None
    rolling_mean: float | None = None
    ewma: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None


class TrendSummary(BaseModel):
    latest: float | None = None
    previous: float | None = None
    target_current: float | None = None
    mean: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    delta: float | None = None
    slope_15m: float | None = None
    slope_1h: float | None = None
    zscore_1h: float | None = None
    std_1h: float | None = None


class SignalTrendResponse(BaseModel):
    signal: str
    label: str
    subsystem: str
    unit: str | None = None
    range_unit: str = "hours"
    range_value: int = 6
    bucket: str = "raw"
    count: int = 0
    target_signal: str | None = None
    target_label: str | None = None
    target_value: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    summary: TrendSummary = Field(default_factory=TrendSummary)
    points: list[TrendPoint] = Field(default_factory=list)
    rules: list[TrendRuleSummary] = Field(default_factory=list)


class MultiSignalTrendResponse(BaseModel):
    signals: list[str] = Field(default_factory=list)
    range_unit: str = "hours"
    range_value: int = 6
    bucket: str = "raw"
    correlation_mode: str = "single"
    series: list[SignalTrendResponse] = Field(default_factory=list)


class StatusResponse(BaseModel):
    service_status: str
    data_source: str | None = None
    latest_timestamp: datetime | None = None
    earliest_timestamp: datetime | None = None
    history_rows: int = 0
    recent_alert_events: int = 0
    active_alerts: int = 0
    last_refresh_at: datetime | None = None


class AiStatusResponse(BaseModel):
    enabled: bool
    has_api_key: bool
    model: str
    eligible_alerts: int = 0
    alerts_with_ai: int = 0
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_signal: str | None = None
    last_layer: str | None = None
