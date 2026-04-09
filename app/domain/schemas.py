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


class StatusResponse(BaseModel):
    service_status: str
    data_source: str | None = None
    latest_timestamp: datetime | None = None
    active_alerts: int = 0
    last_refresh_at: datetime | None = None
