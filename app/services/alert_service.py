"""Motor de alertas em camadas para o compressor TA6000."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.mappings import (
    CALIBRATION_HINTS,
    STUCK_SENSOR_SIGNALS,
    SUBSYSTEM_SIGNALS,
    ZERO_ABNORMAL_SIGNALS,
)
from app.domain.schemas import AlertRecord, DataQualityIssue, SubsystemRiskScore


class AlertService:
    """Avalia regras fixas, tendencias e anomalias operacionais."""

    severity_weights = {
        "low": 20.0,
        "medium": 45.0,
        "high": 75.0,
        "critical": 95.0,
    }

    def __init__(self, rules_path: Path) -> None:
        self.rules_path = rules_path
        self.rules = self._load_rules()

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
        return list({alert.alert_id: alert for alert in alerts}.values())

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

            if self._condition_triggered(rule=rule, value=float(feature_value)):
                alerts.append(
                    self._build_alert(
                        rule_id=rule["rule_id"],
                        layer="trend",
                        subsystem=rule["subsystem"],
                        signal=rule["signal"],
                        severity=rule["severity"],
                        title=rule["title"],
                        message=rule["message"],
                        current_value=float(feature_value),
                        threshold=self._threshold_text(rule),
                        mode_key=mode_key,
                        current_ts=current_ts,
                        metadata={"feature": rule["feature"]},
                    )
                )
        return alerts

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
                    severity="medium",
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
                        severity="medium",
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

    @staticmethod
    def _detect_sensor_stuck(
        history_window: pd.DataFrame,
        signal: str,
    ) -> dict[str, Any] | None:
        if signal not in history_window.columns:
            return None
        tail = history_window[signal].dropna().tail(10)
        if len(tail) < 5 or tail.nunique(dropna=True) != 1:
            return None
        return {
            "repeated_value": float(tail.iloc[-1]),
            "window_points": int(len(tail)),
        }

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
