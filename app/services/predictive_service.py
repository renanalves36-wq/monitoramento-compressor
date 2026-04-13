"""Predicao antecipada por metodos estatisticos e enriquecimento opcional com LLM."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import linregress

from app.config import Settings
from app.domain.predictive_rules import PREDICTIVE_RULES
from app.domain.schemas import AlertRecord, LlmInsight, PredictiveDiagnosis
from app.services.gemini_insight_service import GeminiInsightService
from app.services.prescriptive_service import PrescriptiveService


NORMAL_MODE_KEY = "EM FUNCIONAMENTO|CARREGADO"


class PredictiveService:
    """Avalia degradacao e projecao de limiar para antecipar alarme critico ou trip."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rules = PREDICTIVE_RULES
        self.prescriptive_service = PrescriptiveService(settings=settings)
        self.gemini_service = GeminiInsightService(settings=settings)

    def evaluate_current(
        self,
        feature_frame: pd.DataFrame,
        active_alerts: list[AlertRecord],
    ) -> list[AlertRecord]:
        if not self.settings.predictive_alerts_enabled or feature_frame.empty:
            return []

        latest = feature_frame.iloc[-1]
        mode_key = str(latest.get("mode_key", ""))
        if mode_key != NORMAL_MODE_KEY:
            return []

        alerts: list[AlertRecord] = []
        active_signals = {alert.signal for alert in active_alerts if alert.signal}
        for signal, rule in self.rules.items():
            if signal in active_signals:
                continue
            alert = self._evaluate_signal(
                feature_frame=feature_frame,
                latest=latest,
                signal=signal,
                rule=rule,
                mode_key=mode_key,
            )
            if alert is not None:
                alerts.append(alert)

        return alerts

    def _evaluate_signal(
        self,
        *,
        feature_frame: pd.DataFrame,
        latest: pd.Series,
        signal: str,
        rule: dict[str, Any],
        mode_key: str,
    ) -> AlertRecord | None:
        if signal not in feature_frame.columns:
            return None

        lookback_points = int(rule.get("lookback_points", self.settings.predictive_min_points))
        signal_frame = (
            feature_frame[feature_frame["mode_key"] == mode_key]
            .loc[:, ["timestamp", signal]]
            .dropna(subset=["timestamp", signal])
            .sort_values("timestamp")
            .tail(max(lookback_points, self.settings.predictive_min_points))
            .reset_index(drop=True)
        )
        if len(signal_frame) < max(lookback_points, self.settings.predictive_min_points):
            return None

        regression = self._compute_regression(signal_frame=signal_frame, signal=signal)
        if regression is None:
            return None

        latest_value = self._safe_float(latest.get(signal))
        threshold = float(rule["threshold"])
        direction = str(rule["direction"])
        if latest_value is None:
            return None

        closeness_ratio = self._compute_closeness_ratio(
            latest_value=latest_value,
            threshold=threshold,
            direction=direction,
        )
        if closeness_ratio < float(rule.get("min_current_ratio", 0.0)):
            return None

        if not self._is_risky_slope(
            direction=direction,
            slope_per_hour=regression["slope_per_hour"],
            min_slope_per_hour=float(rule.get("min_slope_per_hour", 0.0)),
        ):
            return None

        if regression["r2"] < self.settings.predictive_min_regression_r2:
            return None

        forecast_minutes = self._forecast_minutes_to_threshold(
            direction=direction,
            current_value=latest_value,
            threshold=threshold,
            slope_per_hour=regression["slope_per_hour"],
        )
        forecast_limit = int(rule.get("forecast_horizon_minutes", self.settings.predictive_forecast_horizon_minutes))
        if forecast_minutes is None or forecast_minutes > forecast_limit:
            return None

        feature_map = latest.to_dict()
        zscore_1h = abs(self._safe_float(feature_map.get(f"{signal}__zscore_1h")) or 0.0)
        ewma_gap_abs = self._safe_float(feature_map.get(f"{signal}__ewma_gap_abs")) or 0.0
        degradation_score = self._compute_degradation_score(
            closeness_ratio=closeness_ratio,
            slope_per_hour=regression["slope_per_hour"],
            min_slope_per_hour=float(rule.get("min_slope_per_hour", 1.0)),
            r2=regression["r2"],
            zscore_1h=zscore_1h,
            ewma_gap_abs=ewma_gap_abs,
            threshold=threshold,
            consistency=regression["directional_consistency"],
            forecast_minutes=forecast_minutes,
            forecast_limit=forecast_limit,
        )
        confidence = self._compute_confidence(
            degradation_score=degradation_score,
            r2=regression["r2"],
            consistency=regression["directional_consistency"],
            forecast_minutes=forecast_minutes,
            forecast_limit=forecast_limit,
        )
        if confidence < self.settings.predictive_min_confidence:
            return None

        predicted_event = self._predict_event_type(
            forecast_minutes=forecast_minutes,
            trip_horizon_minutes=int(rule.get("trip_horizon_minutes", self.settings.predictive_trip_horizon_minutes)),
            trip_related=bool(rule.get("trip_related", False)),
        )
        severity = self._predict_severity(
            predicted_event=predicted_event,
            forecast_minutes=forecast_minutes,
            criticality=str(rule.get("criticality", "alta")),
        )

        current_ts = pd.to_datetime(latest["timestamp"]).to_pydatetime()
        predictive_diagnosis = PredictiveDiagnosis(
            signal=signal,
            method="degradation_regression",
            trend_direction=direction,
            degradation_score=round(degradation_score, 1),
            confidence=round(confidence, 3),
            threshold=threshold,
            threshold_label=f"limiar {threshold:g}",
            current_value=latest_value,
            slope_per_hour=round(regression["slope_per_hour"], 4),
            zscore_1h=round(zscore_1h, 4),
            ewma_gap_abs=round(ewma_gap_abs, 4),
            regression_r2=round(regression["r2"], 4),
            directional_consistency=round(regression["directional_consistency"], 4),
            forecast_minutes=round(forecast_minutes, 1),
            predicted_event=predicted_event,
            observations=self._build_predictive_observations(
                signal=signal,
                forecast_minutes=forecast_minutes,
                regression=regression,
                degradation_score=degradation_score,
            ),
        )

        prescriptive_signal = str(rule.get("prescriptive_signal", signal))
        prescriptive = (
            self.prescriptive_service.generate_prescriptive_diagnosis(
                variavel_principal=prescriptive_signal,
                snapshot=latest,
                features=latest,
                contexto_operacional={
                    "mode_key": mode_key,
                    "st_oper": latest.get("st_oper"),
                    "st_carga_oper": latest.get("st_carga_oper"),
                },
            )
            if self.prescriptive_service.supports(prescriptive_signal)
            else None
        )

        title = self._build_title(rule=rule, predicted_event=predicted_event)
        message = self._build_message(
            signal_label=str(rule.get("label", signal)),
            predicted_event=predicted_event,
            forecast_minutes=forecast_minutes,
            latest_value=latest_value,
            threshold=threshold,
        )
        llm_insight = self.gemini_service.generate_predictive_insight(
            signal=signal,
            alert_title=title,
            alert_message=message,
            snapshot=self._build_snapshot_context(latest),
            evidence=predictive_diagnosis.model_dump(),
            prescriptive_diagnosis=None if prescriptive is None else prescriptive.model_dump(),
        )

        return AlertRecord(
            alert_id=self._build_alert_id(signal, predicted_event),
            rule_id=f"predictive::{signal}",
            layer="predictive_statistics",
            subsystem=str(rule["subsystem"]),
            signal=signal,
            severity=severity,
            title=title,
            message=message,
            triggered_at=current_ts,
            last_seen_at=current_ts,
            current_value=round(latest_value, 4),
            threshold=f"{direction} {threshold:g}",
            mode_key=mode_key,
            metadata={
                "forecast_minutes": round(forecast_minutes, 1),
                "degradation_score": round(degradation_score, 1),
                "regression_r2": round(regression["r2"], 4),
                "directional_consistency": round(regression["directional_consistency"], 4),
                "slope_per_hour": round(regression["slope_per_hour"], 4),
                "predicted_event": predicted_event,
            },
            prescriptive_diagnosis=prescriptive,
            predictive_diagnosis=predictive_diagnosis,
            llm_insight=llm_insight,
        )

    @staticmethod
    def _build_alert_id(signal: str, predicted_event: str) -> str:
        return hashlib.sha1(f"predictive::{signal}::{predicted_event}".encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _compute_regression(
        self,
        *,
        signal_frame: pd.DataFrame,
        signal: str,
    ) -> dict[str, float] | None:
        timestamps = pd.to_datetime(signal_frame["timestamp"], errors="coerce")
        values = pd.to_numeric(signal_frame[signal], errors="coerce")
        valid = timestamps.notna() & values.notna()
        if valid.sum() < self.settings.predictive_min_points:
            return None

        ts = timestamps[valid].reset_index(drop=True)
        y = values[valid].astype(float).reset_index(drop=True)
        minutes = (ts - ts.iloc[0]).dt.total_seconds() / 60.0
        if len(minutes) < self.settings.predictive_min_points:
            return None

        result = linregress(minutes, y)
        diffs = y.diff().dropna()
        if diffs.empty:
            return None
        positive_share = float((diffs > 0).mean())
        negative_share = float((diffs < 0).mean())
        return {
            "slope_per_minute": float(result.slope),
            "slope_per_hour": float(result.slope * 60.0),
            "intercept": float(result.intercept),
            "r2": float(result.rvalue**2 if not np.isnan(result.rvalue) else 0.0),
            "directional_consistency": max(positive_share, negative_share),
        }

    @staticmethod
    def _compute_closeness_ratio(
        *,
        latest_value: float,
        threshold: float,
        direction: str,
    ) -> float:
        if threshold == 0:
            return 0.0
        if direction == "up":
            return latest_value / threshold
        return threshold / max(latest_value, 1e-6)

    @staticmethod
    def _is_risky_slope(
        *,
        direction: str,
        slope_per_hour: float,
        min_slope_per_hour: float,
    ) -> bool:
        if direction == "up":
            return slope_per_hour >= min_slope_per_hour
        return slope_per_hour <= -abs(min_slope_per_hour)

    @staticmethod
    def _forecast_minutes_to_threshold(
        *,
        direction: str,
        current_value: float,
        threshold: float,
        slope_per_hour: float,
    ) -> float | None:
        slope_per_minute = slope_per_hour / 60.0
        if abs(slope_per_minute) < 1e-9:
            return None
        if direction == "up":
            if slope_per_minute <= 0 or current_value >= threshold:
                return None
            return (threshold - current_value) / slope_per_minute
        if slope_per_minute >= 0 or current_value <= threshold:
            return None
        return (threshold - current_value) / slope_per_minute

    @staticmethod
    def _compute_degradation_score(
        *,
        closeness_ratio: float,
        slope_per_hour: float,
        min_slope_per_hour: float,
        r2: float,
        zscore_1h: float,
        ewma_gap_abs: float,
        threshold: float,
        consistency: float,
        forecast_minutes: float,
        forecast_limit: float,
    ) -> float:
        closeness_component = min(max(closeness_ratio, 0.0), 1.25) / 1.25
        slope_component = min(abs(slope_per_hour) / max(min_slope_per_hour, 1e-6), 2.0) / 2.0
        zscore_component = min(zscore_1h / 3.0, 1.0)
        drift_component = min(ewma_gap_abs / max(abs(threshold) * 0.03, 0.1), 1.0)
        urgency_component = max(0.0, 1.0 - (forecast_minutes / max(forecast_limit, 1.0)))
        score = (
            closeness_component * 28.0
            + slope_component * 18.0
            + r2 * 18.0
            + consistency * 14.0
            + zscore_component * 12.0
            + drift_component * 5.0
            + urgency_component * 5.0
        )
        return min(100.0, max(0.0, score))

    @staticmethod
    def _compute_confidence(
        *,
        degradation_score: float,
        r2: float,
        consistency: float,
        forecast_minutes: float,
        forecast_limit: float,
    ) -> float:
        urgency = max(0.0, 1.0 - (forecast_minutes / max(forecast_limit, 1.0)))
        return min(
            0.99,
            max(
                0.0,
                (degradation_score / 100.0) * 0.45
                + r2 * 0.25
                + consistency * 0.2
                + urgency * 0.1,
            ),
        )

    @staticmethod
    def _predict_event_type(
        *,
        forecast_minutes: float,
        trip_horizon_minutes: int,
        trip_related: bool,
    ) -> str:
        if trip_related and forecast_minutes <= trip_horizon_minutes:
            return "possible_trip"
        return "critical_alarm"

    @staticmethod
    def _predict_severity(
        *,
        predicted_event: str,
        forecast_minutes: float,
        criticality: str,
    ) -> str:
        if predicted_event == "possible_trip":
            return "critical" if forecast_minutes <= 30 else "high"
        if criticality == "critica":
            return "high"
        return "medium"

    @staticmethod
    def _build_title(rule: dict[str, Any], predicted_event: str) -> str:
        label = str(rule.get("label", "Indicador"))
        if predicted_event == "possible_trip":
            return f"Risco antecipado de trip por tendencia em {label}"
        return f"Risco antecipado de alarme critico em {label}"

    @staticmethod
    def _build_message(
        *,
        signal_label: str,
        predicted_event: str,
        forecast_minutes: float,
        latest_value: float,
        threshold: float,
    ) -> str:
        event_label = "trip" if predicted_event == "possible_trip" else "alarme critico"
        return (
            f"A tendencia estatistica de {signal_label} sugere risco de {event_label} "
            f"em aproximadamente {round(forecast_minutes)} min se a degradacao persistir. "
            f"Valor atual {latest_value:.3f} | limiar {threshold:.3f}."
        )

    @staticmethod
    def _build_predictive_observations(
        *,
        signal: str,
        forecast_minutes: float,
        regression: dict[str, float],
        degradation_score: float,
    ) -> list[str]:
        return [
            f"regressao linear com R2 {regression['r2']:.2f} na janela recente de {signal}.",
            f"consistencia direcional de {regression['directional_consistency']:.2f} na serie recente.",
            f"score de degradacao calculado em {degradation_score:.1f}/100.",
            f"tempo estimado ate o limiar: {forecast_minutes:.1f} min.",
        ]

    @staticmethod
    def _build_snapshot_context(latest: pd.Series) -> dict[str, Any]:
        keys = [
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
        context: dict[str, Any] = {}
        for key in keys:
            value = latest.get(key)
            if value is None or pd.isna(value):
                continue
            if isinstance(value, (np.floating, float)):
                context[key] = round(float(value), 4)
            else:
                context[key] = value
        return context
