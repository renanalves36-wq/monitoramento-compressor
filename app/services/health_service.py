"""Orquestracao entre ingestao, features, alertas e API."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.config import Settings
from app.domain.schemas import (
    AlertsResponse,
    ReadingsResponse,
    RiskScoresResponse,
    SnapshotResponse,
    StatusResponse,
)
from app.services.alert_service import AlertService
from app.services.feature_service import FeatureService
from app.services.ingestion_service import IngestionBatch, IngestionService
from app.storage.alert_repository import AlertRepository
from app.utils.datetime_utils import lookback_datetime, utc_now
from app.utils.logger import get_logger


class HealthService:
    """Executa o ciclo de observabilidade do compressor."""

    def __init__(self, settings: Settings, repository: AlertRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.ingestion_service = IngestionService(settings)
        self.feature_service = FeatureService()
        self.alert_service = AlertService(settings.alert_rules_path)
        self.logger = get_logger(__name__)

        self._history_frame = pd.DataFrame()
        self._feature_frame = pd.DataFrame()
        self._quality_issues = []
        self._risk_scores = self.alert_service._empty_scores()
        self._last_refresh_at: datetime | None = None

    def refresh(self, force: bool = False) -> None:
        if not force and self._last_refresh_at:
            age = (utc_now() - self._last_refresh_at).total_seconds()
            if age < self.settings.cache_ttl_seconds:
                return

        try:
            self._run_cycle()
        except Exception as exc:  # pragma: no cover - seguranca operacional
            self.logger.exception("refresh_failed", extra={"error": str(exc)})

    def _run_cycle(self) -> None:
        batch = self._load_batch()
        if batch.frame.empty and self._history_frame.empty:
            self._last_refresh_at = utc_now()
            return

        if not batch.frame.empty:
            self._history_frame = self._merge_history(batch.frame)
            self._quality_issues = batch.quality_issues

        if self._history_frame.empty:
            self._last_refresh_at = utc_now()
            return

        self._feature_frame = self.feature_service.compute(self._history_frame)
        active_alerts, risk_scores = self.alert_service.evaluate(
            feature_frame=self._feature_frame,
            quality_issues=self._quality_issues,
        )
        self.repository.replace_active_alerts(active_alerts)
        self._risk_scores = risk_scores
        self._last_refresh_at = utc_now()

        self.logger.info(
            "monitoring_cycle_completed",
            extra={
                "history_rows": int(len(self._history_frame)),
                "active_alerts": int(len(active_alerts)),
                "quality_issues": int(len(self._quality_issues)),
            },
        )

    def _load_batch(self) -> IngestionBatch:
        if self._history_frame.empty:
            return self.ingestion_service.fetch_recent_window(
                since=lookback_datetime(self.settings.initial_lookback_hours)
            )

        latest_timestamp = pd.to_datetime(self._history_frame["timestamp"].max()).to_pydatetime()
        return self.ingestion_service.fetch_incremental(since_timestamp=latest_timestamp)

    def _merge_history(self, incremental_frame: pd.DataFrame) -> pd.DataFrame:
        combined = (
            pd.concat([self._history_frame, incremental_frame], ignore_index=True)
            if not self._history_frame.empty
            else incremental_frame.copy()
        )
        combined["timestamp"] = pd.to_datetime(combined["timestamp"], errors="coerce")
        combined = combined.dropna(subset=["timestamp"]).sort_values("timestamp")
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")

        latest_timestamp = pd.to_datetime(combined["timestamp"].max()).to_pydatetime()
        cutoff = latest_timestamp - timedelta(hours=self.settings.initial_lookback_hours)
        combined = combined[combined["timestamp"] >= cutoff].reset_index(drop=True)
        return combined

    def get_latest_snapshot(self) -> SnapshotResponse:
        self.refresh()
        if self._feature_frame.empty:
            return SnapshotResponse()

        latest = self._feature_frame.iloc[-1]
        latest_timestamp = pd.to_datetime(latest["timestamp"]).to_pydatetime()
        relevant_issues = [
            issue
            for issue in self._quality_issues
            if issue.timestamp is None or pd.to_datetime(issue.timestamp) == pd.to_datetime(latest_timestamp)
        ]

        return SnapshotResponse(
            timestamp=latest_timestamp,
            mode_key=str(latest.get("mode_key")),
            st_oper=None if pd.isna(latest.get("st_oper")) else str(latest.get("st_oper")),
            st_carga_oper=None
            if pd.isna(latest.get("st_carga_oper"))
            else str(latest.get("st_carga_oper")),
            values=self._serialize_row(latest, include_features=False),
            data_quality_issues=relevant_issues,
        )

    def get_latest_readings(self, limit: int) -> ReadingsResponse:
        self.refresh()
        if self._feature_frame.empty:
            return ReadingsResponse(count=0, readings=[])

        latest_slice = self._feature_frame.tail(limit).sort_values("timestamp", ascending=False)
        readings = [
            self._serialize_row(row, include_features=False)
            for _, row in latest_slice.iterrows()
        ]
        return ReadingsResponse(count=len(readings), readings=readings)

    def get_active_alerts(self) -> AlertsResponse:
        self.refresh()
        alerts = self.repository.list_alerts(active_only=True)
        return AlertsResponse(count=len(alerts), alerts=alerts)

    def get_risk_scores(self) -> RiskScoresResponse:
        self.refresh()
        return RiskScoresResponse(generated_at=utc_now(), scores=self._risk_scores)

    def get_service_status(self) -> StatusResponse:
        self.refresh()
        latest_ts = None
        if not self._feature_frame.empty:
            latest_ts = pd.to_datetime(self._feature_frame["timestamp"].max()).to_pydatetime()

        return StatusResponse(
            service_status="ok" if latest_ts else "waiting_for_data",
            latest_timestamp=latest_ts,
            active_alerts=len(self.repository.list_alerts(active_only=True)),
            last_refresh_at=self._last_refresh_at,
        )

    @staticmethod
    def _serialize_row(row: pd.Series, include_features: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in row.items():
            if not include_features and "__" in key:
                continue
            payload[key] = HealthService._serialize_value(value)
        return payload

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if pd.isna(value):
            return None
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except TypeError:
                return str(value)
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime().isoformat()
        if hasattr(value, "item"):
            try:
                return value.item()
            except ValueError:
                return str(value)
        return value
