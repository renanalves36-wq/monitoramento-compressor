"""Orquestracao entre ingestao, features, alertas e API."""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Any

import numpy as np
import pandas as pd

from app.config import Settings
from app.domain.mappings import (
    DEFAULT_SIGNAL_BY_SUBSYSTEM,
    DERIVED_SIGNALS,
    SUBSYSTEM_SIGNALS,
    TARGET_SIGNAL_BY_SIGNAL,
    get_signal_label,
    get_signal_unit,
)
from app.domain.schemas import (
    AlertsResponse,
    MultiSignalTrendResponse,
    ReadingsResponse,
    RiskScoresResponse,
    SignalCatalogItem,
    SignalCatalogResponse,
    SignalTrendResponse,
    SnapshotResponse,
    StatusResponse,
    TrendPoint,
    TrendRuleSummary,
    TrendSummary,
    AiStatusResponse,
)
from app.services.alert_service import AlertService
from app.services.feature_service import FeatureService
from app.services.ingestion_service import IngestionBatch, IngestionService
from app.services.predictive_service import PredictiveService
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
        self.alert_service = AlertService(settings.alert_rules_path, settings=settings)
        self.predictive_service = PredictiveService(settings)
        self.logger = get_logger(__name__)

        self._history_frame = pd.DataFrame()
        self._feature_frame = pd.DataFrame()
        self._quality_issues = []
        self._risk_scores = self.alert_service._empty_scores()
        self._active_alerts = []
        self._alert_events = []
        self._last_refresh_at: datetime | None = None
        self._data_source = "unknown"
        self._refresh_lock = Lock()

    def refresh(self, force: bool = False) -> None:
        if not force and self._last_refresh_at:
            age = (utc_now() - self._last_refresh_at).total_seconds()
            if age < self.settings.cache_ttl_seconds:
                return

        with self._refresh_lock:
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
            self._data_source = batch.source
            self._last_refresh_at = utc_now()
            return

        if not batch.frame.empty:
            self._data_source = batch.source
            self._history_frame = self._merge_history(batch.frame)
            self._quality_issues = batch.quality_issues

        if self._history_frame.empty:
            self._data_source = batch.source
            self._last_refresh_at = utc_now()
            return

        self._feature_frame = self.feature_service.compute(self._history_frame)
        active_alerts, event_history, risk_scores = self.alert_service.evaluate_history(
            feature_frame=self._feature_frame,
            quality_issues=self._quality_issues,
        )
        predictive_alerts = self.predictive_service.evaluate_current(
            feature_frame=self._feature_frame,
            active_alerts=active_alerts,
        )
        if predictive_alerts:
            active_alerts = [*active_alerts, *predictive_alerts]
            event_history = sorted(
                [*event_history, *predictive_alerts],
                key=lambda alert: alert.last_seen_at,
                reverse=True,
            )
            risk_scores = self.alert_service._compute_scores(active_alerts)

        llm_candidates = [*active_alerts, *event_history[:12]]
        self.alert_service.enrich_alerts_with_llm(
            llm_candidates,
            self._feature_frame,
            max_count=10,
        )

        self.repository.replace_active_alerts(active_alerts)
        self._active_alerts = active_alerts
        self._alert_events = event_history
        self._risk_scores = risk_scores
        self._last_refresh_at = utc_now()

        self.logger.info(
            "monitoring_cycle_completed",
            extra={
                "history_rows": int(len(self._history_frame)),
                "active_alerts": int(len(active_alerts)),
                "quality_issues": int(len(self._quality_issues)),
                "data_source": self._data_source,
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

        if self._data_source == "demo_csv":
            return combined.reset_index(drop=True)

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

    def get_signal_catalog(self) -> SignalCatalogResponse:
        self.refresh()
        active_alerts = self.repository.list_alerts(active_only=True)
        alert_count_by_signal: dict[str, int] = {}
        for alert in active_alerts:
            if alert.signal:
                alert_count_by_signal[alert.signal] = alert_count_by_signal.get(alert.signal, 0) + 1

        available_columns = set(self._history_frame.columns) | set(self._feature_frame.columns)
        signals: list[SignalCatalogItem] = []
        for subsystem, subsystem_signals in SUBSYSTEM_SIGNALS.items():
            for signal in subsystem_signals:
                if signal not in available_columns:
                    continue
                if signal in self._feature_frame.columns and not pd.api.types.is_numeric_dtype(
                    self._feature_frame[signal]
                ):
                    continue
                lower_limit, upper_limit, target_value, rules = self._get_signal_limits_and_rules(signal)
                default_target_signal = TARGET_SIGNAL_BY_SIGNAL.get(signal)
                signals.append(
                    SignalCatalogItem(
                        signal=signal,
                        label=get_signal_label(signal),
                        subsystem=subsystem,
                        unit=get_signal_unit(signal),
                        is_setpoint=signal.startswith("sp_"),
                        is_derived=signal in DERIVED_SIGNALS,
                        default_target_signal=default_target_signal,
                        default_target_label=(
                            get_signal_label(default_target_signal)
                            if default_target_signal
                            else None
                        ),
                        lower_limit=lower_limit,
                        upper_limit=upper_limit,
                        target_value=target_value,
                        active_alerts=alert_count_by_signal.get(signal, 0),
                    )
                )

        default_signal = None
        for subsystem in ("ar_processo", "lubrificacao", "vibracao", "motor", "operacao"):
            candidate = DEFAULT_SIGNAL_BY_SUBSYSTEM.get(subsystem)
            if candidate and any(item.signal == candidate for item in signals):
                default_signal = candidate
                break
        if default_signal is None and signals:
            default_signal = signals[0].signal

        return SignalCatalogResponse(
            default_signal=default_signal,
            default_window=min(120, max(30, len(self._feature_frame) or 120)),
            subsystems=list(SUBSYSTEM_SIGNALS.keys()),
            severities=["all", "low", "medium", "high", "critical"],
            signals=signals,
        )

    def get_signal_trend(self, signal: str, limit: int = 120) -> SignalTrendResponse:
        return self.get_signal_trend_window(
            signal=signal,
            range_value=max(1, limit),
            range_unit="points",
            bucket="raw",
            max_points=max(60, limit),
        )

    def get_signal_trend_window(
        self,
        signal: str,
        range_value: int = 6,
        range_unit: str = "hours",
        bucket: str = "raw",
        max_points: int = 600,
    ) -> SignalTrendResponse:
        self._ensure_feature_frame_loaded()
        base_frame = self._slice_base_frame(range_value=range_value, range_unit=range_unit)
        return self._build_signal_trend_response(
            signal=signal,
            base_frame=base_frame,
            range_value=range_value,
            range_unit=range_unit,
            bucket=bucket,
            max_points=max_points,
        )

    def get_multi_signal_trend_window(
        self,
        signals: list[str],
        range_value: int = 6,
        range_unit: str = "hours",
        bucket: str = "raw",
        max_points: int = 600,
    ) -> MultiSignalTrendResponse:
        self._ensure_feature_frame_loaded()
        ordered_signals: list[str] = []
        for signal in signals:
            normalized_signal = str(signal).strip()
            if not normalized_signal or normalized_signal in ordered_signals:
                continue
            ordered_signals.append(normalized_signal)
            if len(ordered_signals) >= 6:
                break

        base_frame = self._slice_base_frame(range_value=range_value, range_unit=range_unit)
        series = [
            self._build_signal_trend_response(
                signal=signal,
                base_frame=base_frame,
                range_value=range_value,
                range_unit=range_unit,
                bucket=bucket,
                max_points=max_points,
            )
            for signal in ordered_signals
        ]

        return MultiSignalTrendResponse(
            signals=ordered_signals,
            range_unit=range_unit,
            range_value=range_value,
            bucket=bucket,
            correlation_mode="normalized" if len(ordered_signals) > 1 else "single",
            series=series,
        )

    def _build_signal_trend_response(
        self,
        signal: str,
        base_frame: pd.DataFrame,
        range_value: int,
        range_unit: str,
        bucket: str,
        max_points: int,
    ) -> SignalTrendResponse:
        if (
            base_frame.empty
            or signal not in base_frame.columns
            or not pd.api.types.is_numeric_dtype(base_frame[signal])
        ):
            return SignalTrendResponse(
                signal=signal,
                label=get_signal_label(signal),
                subsystem=self._infer_subsystem(signal),
                unit=get_signal_unit(signal),
                range_unit=range_unit,
                range_value=range_value,
                bucket=bucket,
            )

        trend_frame = base_frame.copy()
        effective_bucket = bucket
        bucketed_frame = self._bucketize_trend_frame(
            frame=trend_frame,
            signal=signal,
            bucket=bucket,
        )
        if bucket != "raw" and bucketed_frame.empty and not trend_frame.empty:
            bucketed_frame = trend_frame.reset_index(drop=True)
            effective_bucket = "raw"
        trend_frame = bucketed_frame
        if trend_frame.empty:
            return SignalTrendResponse(
                signal=signal,
                label=get_signal_label(signal),
                subsystem=self._infer_subsystem(signal),
                unit=get_signal_unit(signal),
                range_unit=range_unit,
                range_value=range_value,
                bucket=effective_bucket,
            )

        trend_frame = self._downsample_trend_frame(trend_frame, max_points=max_points)

        lower_limit, upper_limit, target_value, rules = self._get_signal_limits_and_rules(signal)
        target_signal = TARGET_SIGNAL_BY_SIGNAL.get(signal)
        target_label = get_signal_label(target_signal) if target_signal else None

        points: list[TrendPoint] = []
        for _, row in trend_frame.iterrows():
            row_target_value = target_value
            if target_signal and target_signal in trend_frame.columns:
                row_target_value = self._safe_float(row.get(target_signal))

            points.append(
                TrendPoint(
                    timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                    value=self._safe_float(row.get(signal)),
                    target_value=row_target_value,
                    rolling_mean=self._safe_float(row.get(f"{signal}__ma_15m")),
                    ewma=self._safe_float(row.get(f"{signal}__ewma")),
                    lower_limit=lower_limit,
                    upper_limit=upper_limit,
                )
            )

        latest_row = trend_frame.iloc[-1]
        previous_row = trend_frame.iloc[-2] if len(trend_frame) >= 2 else latest_row
        current_target_value = target_value
        if target_signal and target_signal in trend_frame.columns:
            current_target_value = self._safe_float(latest_row.get(target_signal))
            if current_target_value is None:
                current_target_value = target_value

        summary = TrendSummary(
            latest=self._safe_float(latest_row.get(signal)),
            previous=self._safe_float(previous_row.get(signal)),
            target_current=current_target_value,
            mean=self._safe_float(trend_frame[signal].mean()),
            minimum=self._safe_float(trend_frame[signal].min()),
            maximum=self._safe_float(trend_frame[signal].max()),
            delta=self._safe_float(latest_row.get(signal) - previous_row.get(signal)),
            slope_15m=self._safe_float(latest_row.get(f"{signal}__slope_15m")),
            slope_1h=self._safe_float(latest_row.get(f"{signal}__slope_1h")),
            zscore_1h=self._safe_float(latest_row.get(f"{signal}__zscore_1h")),
            std_1h=self._safe_float(latest_row.get(f"{signal}__std_1h")),
        )

        return SignalTrendResponse(
            signal=signal,
            label=get_signal_label(signal),
            subsystem=self._infer_subsystem(signal),
            unit=get_signal_unit(signal),
            range_unit=range_unit,
            range_value=range_value,
            bucket=effective_bucket,
            count=len(points),
            target_signal=target_signal,
            target_label=target_label,
            target_value=target_value,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            summary=summary,
            points=points,
            rules=rules,
        )

    def get_service_status(self) -> StatusResponse:
        self.refresh()
        earliest_ts = None
        latest_ts = None
        if not self._feature_frame.empty:
            earliest_ts = pd.to_datetime(self._feature_frame["timestamp"].min()).to_pydatetime()
            latest_ts = pd.to_datetime(self._feature_frame["timestamp"].max()).to_pydatetime()

        return StatusResponse(
            service_status="ok" if latest_ts else "waiting_for_data",
            data_source=self._data_source,
            earliest_timestamp=earliest_ts,
            latest_timestamp=latest_ts,
            history_rows=int(len(self._feature_frame)),
            recent_alert_events=int(len(self._alert_events)),
            active_alerts=len(self.repository.list_alerts(active_only=True)),
            last_refresh_at=self._last_refresh_at,
        )

    def get_ai_status(self) -> AiStatusResponse:
        status = self.alert_service.gemini_service.status()
        unique_alerts: dict[str, Any] = {}
        for alert in [*self._active_alerts, *self._alert_events[:50]]:
            unique_alerts[alert.alert_id] = alert
        status["eligible_alerts"] = sum(
            1
            for alert in unique_alerts.values()
            if self.alert_service._supports_llm_enrichment(alert)
        )
        status["alerts_with_ai"] = sum(
            1 for alert in unique_alerts.values() if alert.llm_insight is not None
        )
        return AiStatusResponse.model_validate(status)

    def force_ai_refresh(self) -> AiStatusResponse:
        self.refresh(force=True)
        return self.get_ai_status()

    def get_recent_alerts(
        self,
        limit: int = 50,
        subsystem: str | None = None,
        severity: str | None = None,
    ) -> AlertsResponse:
        self.refresh()
        filtered = self._alert_events
        if subsystem:
            filtered = [alert for alert in filtered if alert.subsystem == subsystem]
        if severity:
            filtered = [alert for alert in filtered if alert.severity == severity]
        filtered = sorted(filtered, key=lambda alert: alert.last_seen_at, reverse=True)
        alerts = filtered[:limit]
        return AlertsResponse(count=len(alerts), alerts=alerts)

    def _ensure_feature_frame_loaded(self) -> None:
        if not self._feature_frame.empty:
            return
        self.refresh()

    def _slice_base_frame(self, range_value: int, range_unit: str) -> pd.DataFrame:
        frame = self._feature_frame.sort_values("timestamp").copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame = frame.dropna(subset=["timestamp"])
        if frame.empty:
            return frame

        if range_unit == "points":
            return frame.tail(range_value).reset_index(drop=True)

        latest_timestamp = pd.to_datetime(frame["timestamp"].max()).to_pydatetime()
        unit_map = {
            "minutes": timedelta(minutes=range_value),
            "hours": timedelta(hours=range_value),
            "days": timedelta(days=range_value),
        }
        delta = unit_map.get(range_unit, timedelta(hours=6))
        start_timestamp = latest_timestamp - delta
        return frame[frame["timestamp"] >= start_timestamp].reset_index(drop=True)

    @staticmethod
    def _downsample_trend_frame(frame: pd.DataFrame, max_points: int) -> pd.DataFrame:
        if frame.empty or max_points <= 0 or len(frame) <= max_points:
            return frame.reset_index(drop=True)

        indices = np.linspace(0, len(frame) - 1, num=max_points, dtype=int)
        return frame.iloc[np.unique(indices)].reset_index(drop=True)

    def _bucketize_trend_frame(
        self,
        frame: pd.DataFrame,
        signal: str,
        bucket: str,
    ) -> pd.DataFrame:
        if frame.empty or bucket == "raw":
            return frame.reset_index(drop=True)

        rule_map = {
            "minutes": "1min",
            "hours": "1h",
            "days": "1D",
        }
        if bucket not in rule_map:
            return frame.reset_index(drop=True)

        frame = frame.copy().set_index("timestamp")
        columns_to_aggregate = {
            signal: "mean",
            f"{signal}__ma_15m": "mean",
            f"{signal}__ewma": "mean",
            f"{signal}__slope_15m": "last",
            f"{signal}__slope_1h": "last",
            f"{signal}__zscore_1h": "last",
            f"{signal}__std_1h": "mean",
            "mode_key": "last",
        }
        target_signal = TARGET_SIGNAL_BY_SIGNAL.get(signal)
        if target_signal and target_signal in frame.columns:
            columns_to_aggregate[target_signal] = "mean"

        aggregate_map = {
            column: agg
            for column, agg in columns_to_aggregate.items()
            if column in frame.columns
        }
        if not aggregate_map:
            return frame.reset_index(drop=True)

        bucketed = (
            frame.resample(rule_map[bucket])
            .agg(aggregate_map)
            .dropna(subset=[signal], how="all")
            .reset_index()
        )
        return bucketed

    def _get_signal_limits_and_rules(
        self, signal: str
    ) -> tuple[float | None, float | None, float | None, list[TrendRuleSummary]]:
        lower_limit: float | None = None
        upper_limit: float | None = None
        target_value: float | None = None
        rules: list[TrendRuleSummary] = []
        between_lower_candidates: list[float] = []
        between_upper_candidates: list[float] = []
        lower_threshold_candidates: list[float] = []
        upper_threshold_candidates: list[float] = []

        for rule in self.alert_service.rules.get("fixed_rules", []):
            if rule.get("signal") != signal:
                continue

            condition = rule.get("condition")
            threshold_text = None
            if condition == "between":
                min_value = float(rule["min_value"])
                max_value = float(rule["max_value"])
                between_lower_candidates.append(min_value)
                between_upper_candidates.append(max_value)
                threshold_text = f"{min_value}..{max_value}"
            elif condition in {"gt", "gte"}:
                candidate = float(rule["threshold"])
                upper_threshold_candidates.append(candidate)
                threshold_text = f"{condition} {candidate}"
            elif condition in {"lt", "lte"}:
                candidate = float(rule["threshold"])
                lower_threshold_candidates.append(candidate)
                threshold_text = f"{condition} {candidate}"

            rules.append(
                TrendRuleSummary(
                    rule_id=rule["rule_id"],
                    title=rule["title"],
                    severity=rule["severity"],
                    layer="fixed_rule",
                    condition=condition,
                    threshold=threshold_text,
                )
            )

        for rule in self.alert_service.rules.get("trend_rules", []):
            if rule.get("signal") != signal:
                continue
            rules.append(
                TrendRuleSummary(
                    rule_id=rule["rule_id"],
                    title=rule["title"],
                    severity=rule["severity"],
                    layer="trend",
                    condition=rule.get("condition"),
                    threshold=(
                        None
                        if "threshold" not in rule
                        else f"{rule.get('condition')} {rule.get('threshold')}"
                    ),
                )
            )

        if between_lower_candidates:
            lower_limit = max(between_lower_candidates)
        elif lower_threshold_candidates:
            lower_limit = max(lower_threshold_candidates)

        if between_upper_candidates:
            upper_limit = min(between_upper_candidates)
        elif upper_threshold_candidates:
            upper_limit = min(upper_threshold_candidates)

        if signal in TARGET_SIGNAL_BY_SIGNAL:
            target_value = None

        return lower_limit, upper_limit, target_value, rules

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _infer_subsystem(signal: str) -> str:
        for subsystem, signals in SUBSYSTEM_SIGNALS.items():
            if signal in signals:
                return subsystem
        return "operacao"

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
