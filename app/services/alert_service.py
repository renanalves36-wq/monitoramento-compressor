"""Motor de alertas em camadas para o compressor TA6000."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings, get_settings
from app.domain.mappings import (
    CALIBRATION_HINTS,
    STUCK_SENSOR_SIGNALS,
    SUBSYSTEM_SIGNALS,
    ZERO_ABNORMAL_SIGNALS,
)
from app.domain.schemas import AlertRecord, DataQualityIssue, SubsystemRiskScore
from app.services.gemini_insight_service import GeminiInsightService
from app.services.prescriptive_service import PrescriptiveService
from app.utils.logger import get_logger


class AlertService:
    """Avalia regras fixas, tendencias e anomalias operacionais."""

    severity_weights = {
        "low": 20.0,
        "medium": 45.0,
        "high": 75.0,
        "critical": 95.0,
    }

    def __init__(self, rules_path: Path, settings: Settings | None = None) -> None:
        self.rules_path = rules_path
        self.settings = settings or get_settings()
        self.rules = self._load_rules()
        self.prescriptive_service = PrescriptiveService(settings=self.settings)
        self.gemini_service = GeminiInsightService(settings=self.settings)
        self.logger = get_logger(__name__)

    def _load_rules(self) -> dict[str, Any]:
        with self.rules_path.open("r", encoding="utf-8") as file_obj:
            return json.load(file_obj)

    def evaluate(
        self,
        feature_frame: pd.DataFrame,
        quality_issues: list[DataQualityIssue],
    ) -> tuple[list[AlertRecord], list[SubsystemRiskScore]]:
        active_alerts, _event_history, scores = self.evaluate_history(
            feature_frame=feature_frame,
            quality_issues=quality_issues,
        )
        return active_alerts, scores

    def evaluate_history(
        self,
        feature_frame: pd.DataFrame,
        quality_issues: list[DataQualityIssue],
    ) -> tuple[list[AlertRecord], list[AlertRecord], list[SubsystemRiskScore]]:
        if feature_frame.empty:
            return [], [], self._empty_scores()

        sorted_frame = feature_frame.sort_values("timestamp").reset_index(drop=True)
        latest_index = len(sorted_frame) - 1

        open_events: dict[str, AlertRecord] = {}
        event_history: list[AlertRecord] = []

        for idx, row in sorted_frame.iterrows():
            history_window = sorted_frame.iloc[max(0, idx - 180) : idx + 1]
            snapshot_alerts = self._evaluate_snapshot(
                latest=row,
                history_window=history_window,
                quality_issues=quality_issues if idx == latest_index else [],
            )
            snapshot_map = {alert.alert_id: alert for alert in snapshot_alerts}

            for alert_id in list(open_events.keys()):
                if alert_id not in snapshot_map:
                    closed = open_events.pop(alert_id)
                    closed.is_active = False
                    event_history.append(closed)

            for alert_id, alert in snapshot_map.items():
                if alert_id in open_events:
                    open_event = open_events[alert_id]
                    open_event.last_seen_at = alert.last_seen_at
                    open_event.current_value = alert.current_value
                    open_event.metadata = alert.metadata
                    open_event.threshold = alert.threshold
                    open_event.mode_key = alert.mode_key
                    open_event.prescriptive_diagnosis = alert.prescriptive_diagnosis
                    continue
                open_events[alert_id] = alert.model_copy()

        active_alerts = list(open_events.values())
        for alert in active_alerts:
            alert.is_active = True
            event_history.append(alert)

        event_history = sorted(
            event_history,
            key=lambda alert: (
                alert.last_seen_at,
                self.severity_weights.get(alert.severity, 0.0),
            ),
            reverse=True,
        )
        active_alerts = sorted(
            active_alerts,
            key=lambda alert: (
                alert.last_seen_at,
                self.severity_weights.get(alert.severity, 0.0),
            ),
            reverse=True,
        )
        scores = self._compute_scores(active_alerts)
        return active_alerts, event_history, scores

    def _evaluate_snapshot(
        self,
        latest: pd.Series,
        history_window: pd.DataFrame,
        quality_issues: list[DataQualityIssue],
    ) -> list[AlertRecord]:
        current_ts = pd.to_datetime(latest["timestamp"]).to_pydatetime()
        mode_key = str(latest["mode_key"])

        alerts: list[AlertRecord] = []
        alerts.extend(
            self._evaluate_fixed_rules(
                latest=latest,
                current_ts=current_ts,
                mode_key=mode_key,
            )
        )
        alerts.extend(
            self._evaluate_trend_rules(
                latest=latest,
                current_ts=current_ts,
                mode_key=mode_key,
            )
        )
        alerts.extend(
            self._evaluate_anomaly_rules(
                latest=latest,
                current_ts=current_ts,
                mode_key=mode_key,
                history_window=history_window,
                quality_issues=quality_issues,
            )
        )
        deduplicated_alerts = list({alert.alert_id: alert for alert in alerts}.values())
        for alert in deduplicated_alerts:
            if not alert.signal or not self.prescriptive_service.supports(alert.signal):
                continue
            alert.prescriptive_diagnosis = self.prescriptive_service.generate_prescriptive_diagnosis(
                variavel_principal=alert.signal,
                snapshot=latest,
                features=latest,
                contexto_operacional={
                    "mode_key": mode_key,
                    "st_oper": latest.get("st_oper"),
                    "st_carga_oper": latest.get("st_carga_oper"),
                },
            )
        return deduplicated_alerts

    def _evaluate_fixed_rules(
        self, latest: pd.Series, current_ts: datetime, mode_key: str
    ) -> list[AlertRecord]:
        alerts: list[AlertRecord] = []
        for rule in self.rules.get("fixed_rules", []):
            if not self._is_allowed(rule=rule, mode_key=mode_key):
                continue
            signal = rule["signal"]
            value = latest.get(signal)
            if pd.isna(value):
                continue
            if self._condition_triggered(rule=rule, value=float(value)):
                alerts.append(
                    self._build_alert(
                        rule_id=rule["rule_id"],
                        layer="fixed_rule",
                        subsystem=rule["subsystem"],
                        signal=signal,
                        severity=rule["severity"],
                        title=rule["title"],
                        message=rule["message"],
                        current_value=value,
                        threshold=self._threshold_text(rule),
                        mode_key=mode_key,
                        current_ts=current_ts,
                        metadata={"condition": rule["condition"]},
                    )
                )
        return alerts

    def _evaluate_trend_rules(
        self, latest: pd.Series, current_ts: datetime, mode_key: str
    ) -> list[AlertRecord]:
        alerts: list[AlertRecord] = []
        for rule in self.rules.get("trend_rules", []):
            if not self._is_allowed(rule=rule, mode_key=mode_key):
                continue

            feature_name = f"{rule['signal']}__{rule['feature']}"
            feature_value = latest.get(feature_name)
            if feature_value is None or pd.isna(feature_value):
                continue

            passes_guardrails, guardrail_metadata = self._passes_trend_guardrails(
                latest=latest,
                rule=rule,
                feature_value=float(feature_value),
            )
            if self._condition_triggered(rule=rule, value=float(feature_value)) and passes_guardrails:
                raw_signal_value = latest.get(rule["signal"])
                alerts.append(
                    self._build_alert(
                        rule_id=rule["rule_id"],
                        layer="trend",
                        subsystem=rule["subsystem"],
                        signal=rule["signal"],
                        severity=rule["severity"],
                        title=rule["title"],
                        message=rule["message"],
                        current_value=(
                            None if pd.isna(raw_signal_value) else self._normalize_value(raw_signal_value)
                        ),
                        threshold=self._threshold_text(rule),
                        mode_key=mode_key,
                        current_ts=current_ts,
                        metadata={
                            "feature": rule["feature"],
                            "feature_value": float(feature_value),
                            "signal_value": (
                                None if pd.isna(raw_signal_value) else self._normalize_value(raw_signal_value)
                            ),
                            **guardrail_metadata,
                        },
                    )
                )
        return alerts

    def _passes_trend_guardrails(
        self,
        *,
        latest: pd.Series,
        rule: dict[str, Any],
        feature_value: float,
    ) -> tuple[bool, dict[str, Any]]:
        signal = str(rule["signal"])
        feature = str(rule["feature"])
        raw_value = self._safe_float(latest.get(signal))
        ma_15m = self._safe_float(latest.get(f"{signal}__ma_15m"))
        ma_1h = self._safe_float(latest.get(f"{signal}__ma_1h"))
        std_1h = self._safe_float(latest.get(f"{signal}__std_1h"))
        ewma = self._safe_float(latest.get(f"{signal}__ewma"))

        metadata = {
            "feature_label": self._trend_feature_label(feature),
            "analysis_label": (
                "tendencia anormal" if feature.startswith("slope") else "comportamento anormal"
            ),
            "reference_value": ma_1h,
        }
        if raw_value is None:
            return False, metadata

        if feature in {"slope_15m", "slope_1h"}:
            baseline = ma_1h if ma_1h is not None else ma_15m
            if baseline is None:
                return False, metadata

            is_upward = feature_value > 0
            aligned = self._is_trend_alignment_consistent(
                raw_value=raw_value,
                ma_15m=ma_15m,
                ma_1h=ma_1h,
                is_upward=is_upward,
            )
            gap_threshold = max(
                self._noise_floor(baseline),
                0.0 if std_1h is None else std_1h,
            )
            raw_gap = abs(raw_value - baseline)
            if not aligned or raw_gap < gap_threshold:
                return False, metadata

            metadata["analysis_reason"] = (
                "subida sustentada acima do comportamento recente"
                if is_upward
                else "queda sustentada abaixo do comportamento recente"
            )
            metadata["reference_value"] = baseline
            metadata["reference_label"] = "media da ultima hora"
            return True, metadata

        if feature == "zscore_1h":
            if ma_1h is None or std_1h is None:
                return False, metadata
            if std_1h < self._noise_floor(ma_1h, minimum=0.01, ratio=0.005):
                return False, metadata

            raw_gap = abs(raw_value - ma_1h)
            abnormal_gap = max(std_1h * 1.2, self._noise_floor(ma_1h))
            if raw_gap < abnormal_gap:
                return False, metadata

            metadata["analysis_reason"] = "valor fora do comportamento normal recente"
            metadata["reference_label"] = "media da ultima hora"
            return True, metadata

        if feature == "ewma_gap_abs":
            baseline = ewma if ewma is not None else ma_1h
            if baseline is None:
                return False, metadata

            raw_gap = abs(raw_value - baseline)
            abnormal_gap = max(
                self._noise_floor(baseline, minimum=0.1, ratio=0.03),
                0.0 if std_1h is None else std_1h,
            )
            if raw_gap < abnormal_gap:
                return False, metadata

            metadata["analysis_reason"] = "desvio relevante em relacao ao comportamento recente"
            metadata["reference_value"] = baseline
            metadata["reference_label"] = "referencia recente"
            return True, metadata

        return True, metadata

    def _evaluate_anomaly_rules(
        self,
        latest: pd.Series,
        current_ts: datetime,
        mode_key: str,
        history_window: pd.DataFrame,
        quality_issues: list[DataQualityIssue],
    ) -> list[AlertRecord]:
        alerts: list[AlertRecord] = []
        quality_by_signal: dict[tuple[str, str], DataQualityIssue] = {
            (issue.issue_type, issue.signal or ""): issue for issue in quality_issues
        }
        generated_stuck_signals: set[str] = set()

        for signal in STUCK_SENSOR_SIGNALS:
            details = self._detect_sensor_stuck(history_window=history_window, signal=signal)
            if details is None:
                continue
            generated_stuck_signals.add(signal)
            alerts.append(
                self._build_alert(
                    rule_id=f"sensor_stuck::{signal}",
                    layer="operational_anomaly",
                    subsystem=self._infer_subsystem(signal),
                    signal=signal,
                    severity="low",
                    title=f"Possivel sensor travado: {signal}",
                    message="Possivel sensor travado por repeticao persistente do mesmo valor.",
                    current_value=details.get("repeated_value"),
                    threshold="variacao esperada > 0",
                    mode_key=mode_key,
                    current_ts=current_ts,
                    metadata=details,
                )
            )

        for issue in quality_issues:
            if issue.issue_type == "sensor_stuck" and issue.signal and issue.signal not in generated_stuck_signals:
                alerts.append(
                    self._build_alert(
                        rule_id=f"sensor_stuck::{issue.signal}",
                        layer="operational_anomaly",
                        subsystem=self._infer_subsystem(issue.signal),
                        signal=issue.signal,
                        severity="low",
                        title=f"Possivel sensor travado: {issue.signal}",
                        message=issue.message,
                        current_value=issue.details.get("repeated_value"),
                        threshold="variacao esperada > 0",
                        mode_key=mode_key,
                        current_ts=current_ts,
                        metadata=issue.details,
                    )
                )

        for rule in self.rules.get("anomaly_rules", []):
            signal = rule["signal"]
            issue_key = (rule["type"], signal)
            issue = quality_by_signal.get(issue_key)

            should_trigger = issue is not None
            if rule["type"] == "zero_abnormal":
                details = self._detect_zero_abnormal(history_window=history_window, signal=signal)
                should_trigger = should_trigger or details is not None
                if issue is None and details is not None:
                    issue = DataQualityIssue(
                        issue_type="zero_abnormal",
                        signal=signal,
                        timestamp=current_ts,
                        message="Valor zerado recorrente detectado para uma variavel sensivel.",
                        details=details,
                    )
            if rule["type"] == "engineering_hint":
                should_trigger = self._has_engineering_inconsistency(latest=latest, signal=signal)

            if not should_trigger:
                continue

            message = rule["message"]
            if signal in CALIBRATION_HINTS:
                message = f"{message} {CALIBRATION_HINTS[signal]}"

            alerts.append(
                self._build_alert(
                    rule_id=rule["rule_id"],
                    layer="operational_anomaly",
                    subsystem=rule["subsystem"],
                    signal=signal,
                    severity=rule["severity"],
                    title=rule["title"],
                    message=message,
                    current_value=None if pd.isna(latest.get(signal)) else latest.get(signal),
                    threshold=rule["type"],
                    mode_key=mode_key,
                    current_ts=current_ts,
                    metadata={} if issue is None else issue.details,
                )
            )

        return alerts

    def _detect_sensor_stuck(
        self,
        history_window: pd.DataFrame,
        signal: str,
    ) -> dict[str, Any] | None:
        if signal not in history_window.columns or "timestamp" not in history_window.columns:
            return None
        candidate = (
            history_window.loc[:, ["timestamp", signal]]
            .dropna(subset=[signal])
            .sort_values("timestamp")
            .tail(self.settings.sensor_stuck_min_points)
        )
        if len(candidate) < self.settings.sensor_stuck_min_points:
            return None
        duration_minutes = self._estimate_observed_window_minutes(candidate["timestamp"])
        if duration_minutes < float(self.settings.sensor_stuck_min_duration_minutes):
            return None
        values = pd.to_numeric(candidate[signal], errors="coerce").dropna()
        if len(values) < self.settings.sensor_stuck_min_points:
            return None
        repeated_value = float(values.iloc[-1])
        range_value = float(values.max() - values.min())
        std_value = float(values.std(ddof=0))
        range_threshold = max(
            abs(repeated_value) * self.settings.sensor_stuck_relative_range_tolerance,
            self.settings.sensor_stuck_absolute_range_tolerance,
        )
        if range_value > range_threshold or std_value > (range_threshold / 2.0):
            return None
        return {
            "repeated_value": repeated_value,
            "window_points": int(len(values)),
            "window_minutes": round(duration_minutes, 1),
            "observed_range": round(range_value, 6),
            "observed_std": round(std_value, 6),
        }

    @staticmethod
    def _estimate_observed_window_minutes(timestamps: pd.Series) -> float:
        if len(timestamps) <= 1:
            return 0.0
        ordered = pd.to_datetime(timestamps, errors="coerce").dropna().sort_values().reset_index(drop=True)
        if len(ordered) <= 1:
            return 0.0
        duration_minutes = (ordered.iloc[-1] - ordered.iloc[0]).total_seconds() / 60.0
        step_minutes = ordered.diff().dropna().dt.total_seconds().median() / 60.0
        return duration_minutes + (0.0 if pd.isna(step_minutes) else float(step_minutes))

    @staticmethod
    def _detect_zero_abnormal(
        history_window: pd.DataFrame,
        signal: str,
    ) -> dict[str, Any] | None:
        if signal not in ZERO_ABNORMAL_SIGNALS or signal not in history_window.columns:
            return None
        tail = history_window[signal].dropna().tail(5)
        if len(tail) < 3 or not bool((tail == 0).all()):
            return None
        return {"window_points": int(len(tail))}

    def _has_engineering_inconsistency(self, latest: pd.Series, signal: str) -> bool:
        value = latest.get(signal)
        if value is None or pd.isna(value):
            return False

        for rule in self.rules.get("fixed_rules", []):
            if rule["signal"] != signal or rule.get("condition") != "between":
                continue
            min_value = rule["min_value"]
            max_value = rule["max_value"]
            numeric = float(value)
            if numeric < min_value or numeric > max_value:
                return True
        return False

    def _build_alert(
        self,
        rule_id: str,
        layer: str,
        subsystem: str,
        signal: str | None,
        severity: str,
        title: str,
        message: str,
        current_value: Any,
        threshold: str | None,
        mode_key: str,
        current_ts: datetime,
        metadata: dict[str, Any],
    ) -> AlertRecord:
        fingerprint = "|".join([rule_id, subsystem, signal or "", layer])
        alert_id = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()
        return AlertRecord(
            alert_id=alert_id,
            rule_id=rule_id,
            layer=layer,
            subsystem=subsystem,
            signal=signal,
            severity=severity,
            title=title,
            message=message,
            triggered_at=current_ts,
            last_seen_at=current_ts,
            current_value=None if current_value is None else self._normalize_value(current_value),
            threshold=threshold,
            mode_key=mode_key,
            metadata=metadata,
        )

    def enrich_alerts_with_llm(
        self,
        alerts: list[AlertRecord],
        feature_frame: pd.DataFrame,
        *,
        max_count: int = 8,
    ) -> None:
        if not alerts or feature_frame.empty:
            return
        if not self.gemini_service.enabled():
            self.logger.info(
                "gemini_enrichment_skipped",
                extra={
                    "reason": "disabled_or_missing_key",
                    "gemini_enabled": self.settings.gemini_enabled,
                    "has_api_key": bool(self.settings.gemini_api_key),
                },
            )
            return

        ordered_candidates: list[AlertRecord] = []
        seen_ids: set[str] = set()
        for alert in sorted(
            alerts,
            key=lambda item: (
                item.is_active,
                self.severity_weights.get(item.severity, 0.0),
                item.last_seen_at,
            ),
            reverse=True,
        ):
            if alert.alert_id in seen_ids or not self._supports_llm_enrichment(alert):
                continue
            seen_ids.add(alert.alert_id)
            ordered_candidates.append(alert)
            if len(ordered_candidates) >= max_count:
                break

        if not ordered_candidates:
            self.logger.info(
                "gemini_enrichment_skipped",
                extra={"reason": "no_supported_alert_candidates", "alert_count": len(alerts)},
            )
            return

        ordered_frame = feature_frame.copy()
        ordered_frame["timestamp"] = pd.to_datetime(ordered_frame["timestamp"], errors="coerce")
        ordered_frame = ordered_frame.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        for alert in ordered_candidates:
            if alert.llm_insight is not None:
                continue
            snapshot = self._find_snapshot_for_alert(ordered_frame, alert.last_seen_at)
            if snapshot is None:
                continue
            alert.llm_insight = self.gemini_service.generate_alert_insight(
                layer=alert.layer,
                signal=alert.signal or alert.rule_id,
                alert_title=alert.title,
                alert_message=alert.message,
                snapshot=self._build_snapshot_context(snapshot),
                evidence=self._build_alert_evidence(alert),
                prescriptive_diagnosis=(
                    None if alert.prescriptive_diagnosis is None else alert.prescriptive_diagnosis.model_dump()
                ),
                predictive_diagnosis=(
                    None if alert.predictive_diagnosis is None else alert.predictive_diagnosis.model_dump()
                ),
                cache_key=self._build_llm_cache_key(alert),
            )
            if alert.llm_insight is not None:
                self.logger.info(
                    "gemini_alert_insight_attached",
                    extra={
                        "signal": alert.signal,
                        "layer": alert.layer,
                        "rule_id": alert.rule_id,
                    },
                )

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, (int, float, str)):
            return value
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _noise_floor(value: float, *, minimum: float = 0.05, ratio: float = 0.02) -> float:
        return max(abs(value) * ratio, minimum)

    @staticmethod
    def _is_trend_alignment_consistent(
        *,
        raw_value: float,
        ma_15m: float | None,
        ma_1h: float | None,
        is_upward: bool,
    ) -> bool:
        if ma_15m is None or ma_1h is None:
            return True
        if is_upward:
            return raw_value >= ma_15m >= ma_1h
        return raw_value <= ma_15m <= ma_1h

    @staticmethod
    def _trend_feature_label(feature: str) -> str:
        labels = {
            "slope_15m": "ritmo de subida/queda nos ultimos 15 min",
            "slope_1h": "ritmo de subida/queda na ultima hora",
            "zscore_1h": "distancia do comportamento normal na ultima hora",
            "ewma_gap_abs": "distancia do comportamento recente",
        }
        return labels.get(feature, feature)

    @staticmethod
    def _supports_llm_enrichment(alert: AlertRecord) -> bool:
        if alert.layer in {"fixed_rule", "trend", "predictive_statistics"}:
            return True
        if alert.layer == "operational_anomaly" and not str(alert.rule_id).startswith("sensor_stuck::"):
            return True
        return False

    @staticmethod
    def _find_snapshot_for_alert(
        feature_frame: pd.DataFrame,
        timestamp: datetime,
    ) -> pd.Series | None:
        ts = pd.to_datetime(timestamp, errors="coerce")
        if pd.isna(ts) or feature_frame.empty:
            return None
        eligible = feature_frame[feature_frame["timestamp"] <= ts]
        if eligible.empty:
            return None
        return eligible.iloc[-1]

    def _build_alert_evidence(self, alert: AlertRecord) -> dict[str, Any]:
        evidence = {
            "layer": alert.layer,
            "severity": alert.severity,
            "rule_id": alert.rule_id,
            "signal": alert.signal,
            "threshold": alert.threshold,
            "mode_key": alert.mode_key,
            "current_value": alert.current_value,
            "metadata": alert.metadata,
        }
        if alert.predictive_diagnosis is not None:
            evidence["predictive_diagnosis"] = alert.predictive_diagnosis.model_dump()
        return evidence

    @staticmethod
    def _build_llm_cache_key(alert: AlertRecord) -> str:
        return "|".join(
            [
                alert.alert_id,
                alert.rule_id,
                alert.layer,
                alert.signal or "",
            ]
        )

    @staticmethod
    def _build_snapshot_context(latest: pd.Series) -> dict[str, Any]:
        context: dict[str, Any] = {}
        interesting_keys = [
            "timestamp",
            "mode_key",
            "st_oper",
            "st_carga_oper",
            "pv_pres_sistema_bar",
            "pv_pres_descarga_bar",
            "pv_temp_oleo_lubrificacao_c",
            "pv_vib_estagio_1_mils",
            "pv_vib_estagio_2_mils",
            "pv_vib_estagio_3_mils",
            "pv_corr_motor_a",
            "pv_temp_fase_a_do_estator_c",
            "pv_temp_fase_b_do_estator_c",
            "pv_temp_fase_c_do_estator_c",
            "pv_temp_rolamento_dianteiro_motor",
            "pv_pos_abert_valv_admissao_pct",
            "pv_pos_valv_bypass_pct",
            "pv_pos_alivio_pct",
            "delta_filtro_oleo_bar",
        ]
        for key in interesting_keys:
            value = latest.get(key)
            if value is None or pd.isna(value):
                continue
            if hasattr(value, "isoformat"):
                context[key] = value.isoformat()
            elif isinstance(value, (int, float)):
                context[key] = round(float(value), 4)
            else:
                context[key] = str(value)
        return context

    @staticmethod
    def _is_allowed(rule: dict[str, Any], mode_key: str) -> bool:
        allowed = rule.get("allowed_modes", [])
        return not allowed or mode_key in allowed

    @staticmethod
    def _condition_triggered(rule: dict[str, Any], value: float) -> bool:
        condition = rule["condition"]
        if condition == "gt":
            return value > float(rule["threshold"])
        if condition == "gte":
            return value >= float(rule["threshold"])
        if condition == "lt":
            return value < float(rule["threshold"])
        if condition == "lte":
            return value <= float(rule["threshold"])
        if condition == "between":
            return not (float(rule["min_value"]) <= value <= float(rule["max_value"]))
        raise ValueError(f"Unsupported condition: {condition}")

    @staticmethod
    def _threshold_text(rule: dict[str, Any]) -> str:
        if rule["condition"] == "between":
            return f"{rule['min_value']}..{rule['max_value']}"
        return f"{rule['condition']} {rule['threshold']}"

    @classmethod
    def _compute_scores(cls, alerts: list[AlertRecord]) -> list[SubsystemRiskScore]:
        grouped: dict[str, list[AlertRecord]] = {subsystem: [] for subsystem in SUBSYSTEM_SIGNALS}
        for alert in alerts:
            grouped.setdefault(alert.subsystem, []).append(alert)

        scores: list[SubsystemRiskScore] = []
        for subsystem, subsystem_alerts in grouped.items():
            if not subsystem_alerts:
                scores.append(
                    SubsystemRiskScore(
                        subsystem=subsystem,
                        score=0.0,
                        active_alerts=0,
                        highest_severity=None,
                        rationale=[],
                    )
                )
                continue

            weights = [cls.severity_weights.get(alert.severity, 10.0) for alert in subsystem_alerts]
            highest = max(subsystem_alerts, key=lambda item: cls.severity_weights.get(item.severity, 0.0))
            raw_score = max(weights) + max(0, len(subsystem_alerts) - 1) * 8.0
            scores.append(
                SubsystemRiskScore(
                    subsystem=subsystem,
                    score=round(min(100.0, raw_score), 1),
                    active_alerts=len(subsystem_alerts),
                    highest_severity=highest.severity,
                    rationale=[alert.title for alert in subsystem_alerts[:3]],
                )
            )

        return sorted(scores, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _empty_scores() -> list[SubsystemRiskScore]:
        return [
            SubsystemRiskScore(
                subsystem=subsystem,
                score=0.0,
                active_alerts=0,
                highest_severity=None,
                rationale=[],
            )
            for subsystem in SUBSYSTEM_SIGNALS
        ]

    @staticmethod
    def _infer_subsystem(signal: str) -> str:
        for subsystem, signals in SUBSYSTEM_SIGNALS.items():
            if signal in signals:
                return subsystem
        return "operacao"
